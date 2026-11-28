import subprocess
import sys

import jsii
from aws_cdk import (
    Annotations,
    BundlingOptions,
    CfnOutput,
    Duration,
    ILocalBundling,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_route53_targets as targets
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from stacks.bundle import BACKEND_DIR, REPO_ROOT, UNUSED_PATHS
from stacks.stage import ZONE_NAME, Stage

FRONTEND_DIST = REPO_ROOT / "frontend" / "dist" / "frontend" / "browser"
BUNDLE_SCRIPT = REPO_ROOT / "infra" / "stacks" / "bundle.py"

LAMBDA_RUNTIME = lambda_.Runtime.PYTHON_3_13

# AWS Lambda Web Adapter (github.com/awslabs/aws-lambda-web-adapter): runs the
# unchanged FastAPI app on Lambda and streams its responses.
WEB_ADAPTER_LAYER = "arn:aws:lambda:{region}:753240598075:layer:LambdaAdapterLayerArm64:30"

# Angular routes like /stories/3 have no file in S3: serve index.html for any path
# without a file extension, and let the Angular router take it from there.
SPA_REWRITE_JS = """
function handler(event) {
  var request = event.request;
  if (!request.uri.includes('.')) {
    request.uri = '/index.html';
  }
  return request;
}
"""


@jsii.implements(ILocalBundling)
class PipLocalBundling:
    """Bundles the Lambda without Docker, using the local pip to fetch Linux arm64 wheels.

    Runs stacks/bundle.py as a separate process. This code runs inside the CDK, which
    talks to its Node.js engine over a pipe; processes forked from here (as parallel
    compiling did on Linux) inherit that pipe and break it when they exit
    ("@jsii/kernel.RuntimeError: unexpected EOF").
    """

    def try_bundle(self, output_dir: str, *args, **kwargs) -> bool:
        subprocess.run([sys.executable, str(BUNDLE_SCRIPT), output_dir], check=True)
        return True


class SiteStack(Stack):
    """Angular on S3 + CloudFront; FastAPI on Lambda behind a streaming Function URL,
    served together on a subdomain of ukdoshi.com."""

    def __init__(self, scope: Construct, construct_id: str, *, stage: Stage, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        zone = route53.HostedZone.from_lookup(self, "Zone", domain_name=ZONE_NAME)

        # --- Secrets ---
        # CloudFront sends this with every API request, and the API refuses requests
        # without it, so the public Function URL can't be used to skip CloudFront.
        origin_secret = secretsmanager.Secret(
            self,
            "OriginSecret",
            description=f"Header value CloudFront sends to the {stage.site_domain} API",
            generate_secret_string=secretsmanager.SecretStringGenerator(password_length=48, exclude_punctuation=True),
            removal_policy=RemovalPolicy.DESTROY,
        )
        # Created by scripts/claude-key.sh and scripts/database-url.sh before the first
        # deploy, so the app has them from its first start. Looked up here by name.
        claude_key = secretsmanager.Secret.from_secret_name_v2(
            self, "ClaudeApiKey", stage.secret_name("claude-api-key")
        )
        database_url = secretsmanager.Secret.from_secret_name_v2(
            self, "DatabaseUrl", stage.secret_name("database-url")
        )
        # Optional: made by scripts/langfuse-keys.sh. Until it exists, tracing is simply off.
        langfuse_keys = secretsmanager.Secret.from_secret_name_v2(
            self, "LangfuseKeys", stage.secret_name("langfuse-keys")
        )

        # --- Backend: FastAPI on Lambda, via the Web Adapter, with a streaming URL ---
        api_fn = lambda_.Function(
            self,
            "ApiFunction",
            function_name=f"{stage.prefix}-api",
            runtime=LAMBDA_RUNTIME,
            architecture=lambda_.Architecture.ARM_64,
            handler="run.sh",
            code=lambda_.Code.from_asset(
                str(BACKEND_DIR),
                exclude=[".venv", "tests", "**/__pycache__", ".pytest_cache", "*.db"],
                bundling=BundlingOptions(
                    image=LAMBDA_RUNTIME.bundling_image,
                    local=PipLocalBundling(),
                    # Docker fallback, used only if local bundling is unavailable.
                    command=[
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output"
                        + "".join(f" && rm -rf /asset-output/{p}" for p in UNUSED_PATHS)
                        + " && cp -r app run.sh /asset-output/",
                    ],
                ),
            ),
            layers=[
                lambda_.LayerVersion.from_layer_version_arn(
                    self, "WebAdapter", WEB_ADAPTER_LAYER.format(region=self.region)
                )
            ],
            # More memory also means more CPU, which shortens cold starts.
            memory_size=1024,
            # A story takes about 20-30 seconds; the agent (later) runs longer.
            timeout=Duration.minutes(5),
            environment={
                "AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap",
                "AWS_LWA_INVOKE_MODE": "response_stream",
                "AWS_LWA_READINESS_CHECK_PATH": "/api/health",
                "PORT": "8000",
                "ORIGIN_SECRET_ARN": origin_secret.secret_arn,
                "CLAUDE_API_KEY_SECRET": stage.secret_name("claude-api-key"),
                "DATABASE_URL_SECRET": stage.secret_name("database-url"),
                "LANGFUSE_KEYS_SECRET": stage.secret_name("langfuse-keys"),
                "LLM_MODEL": "anthropic/claude-opus-5-5",
                "LLM_REASONING_EFFORT": "low",
                "MAX_STORIES_PER_DAY": "30",
            },
        )
        origin_secret.grant_read(api_fn)
        claude_key.grant_read(api_fn)
        database_url.grant_read(api_fn)
        langfuse_keys.grant_read(api_fn)

        function_url = api_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,  # protected by the origin secret instead
            invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM,
        )

        # --- Frontend: private S3 bucket, only CloudFront can read it ---
        bucket = s3.Bucket(
            self,
            "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        certificate = acm.Certificate(
            self,
            "Certificate",
            domain_name=stage.site_domain,
            validation=acm.CertificateValidation.from_dns(zone),
        )

        spa_rewrite = cloudfront.Function(
            self,
            "SpaRewrite",
            runtime=cloudfront.FunctionRuntime.JS_2_0,
            code=cloudfront.FunctionCode.from_inline(SPA_REWRITE_JS),
        )

        headers = cloudfront.ResponseHeadersPolicy(
            self,
            "SecurityHeaders",
            security_headers_behavior=cloudfront.ResponseSecurityHeadersBehavior(
                strict_transport_security=cloudfront.ResponseHeadersStrictTransportSecurity(
                    access_control_max_age=Duration.days(365), include_subdomains=True, override=True
                ),
                content_type_options=cloudfront.ResponseHeadersContentTypeOptions(override=True),
                frame_options=cloudfront.ResponseHeadersFrameOptions(
                    frame_option=cloudfront.HeadersFrameOption.DENY, override=True
                ),
                referrer_policy=cloudfront.ResponseHeadersReferrerPolicy(
                    referrer_policy=cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
                    override=True,
                ),
            ),
            custom_headers_behavior=None
            if stage.search_engines
            else cloudfront.ResponseCustomHeadersBehavior(
                custom_headers=[cloudfront.ResponseCustomHeader(header="X-Robots-Tag", value="noindex", override=True)]
            ),
        )

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            domain_names=[stage.site_domain],
            certificate=certificate,
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=headers,
                function_associations=[
                    cloudfront.FunctionAssociation(
                        function=spa_rewrite, event_type=cloudfront.FunctionEventType.VIEWER_REQUEST
                    )
                ],
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.FunctionUrlOrigin(
                        function_url,
                        custom_headers={"X-Origin-Verify": origin_secret.secret_value.unsafe_unwrap()},
                        # The longest CloudFront waits between bytes (without a quota
                        # increase). Streams send a keep-alive every 15 seconds.
                        read_timeout=Duration.seconds(60),
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    response_headers_policy=headers,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                    # Never hold back a stream to compress it.
                    compress=False,
                ),
            },
        )

        if FRONTEND_DIST.exists():
            s3deploy.BucketDeployment(
                self,
                "DeployFrontend",
                sources=[s3deploy.Source.asset(str(FRONTEND_DIST))],
                destination_bucket=bucket,
                distribution=distribution,
                distribution_paths=["/*"],
            )
        else:
            Annotations.of(self).add_warning(
                f"{FRONTEND_DIST} not found; run `npm run build` in frontend/ before deploying the site."
            )

        # --- DNS: the site's name aliases to CloudFront (IPv4 + IPv6) ---
        cf_target = route53.RecordTarget.from_alias(targets.CloudFrontTarget(distribution))
        route53.ARecord(self, "SiteA", zone=zone, record_name=stage.site_domain, target=cf_target)
        route53.AaaaRecord(self, "SiteAaaa", zone=zone, record_name=stage.site_domain, target=cf_target)

        CfnOutput(self, "SiteUrl", value=f"https://{stage.site_domain}")
        CfnOutput(self, "CloudFrontUrl", value=f"https://{distribution.distribution_domain_name}")
        CfnOutput(self, "FunctionName", value=api_fn.function_name)
