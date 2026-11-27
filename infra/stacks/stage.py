from dataclasses import dataclass

ZONE_NAME = "ukdoshi.com"  # owned by ukdoshi-site's UkdoshiDns stack; looked up here, never recreated


@dataclass(frozen=True)
class Stage:
    """One copy of Cuddly Tales: its web address and how open it is.

    There is only a live copy for now. A staging copy would be one more Stage
    (e.g. staging.cuddly-tales.ukdoshi.com), plus a branch in the deploy workflow.
    """

    name: str  # "" for live
    site_domain: str
    search_engines: bool = True  # False adds "X-Robots-Tag: noindex" to every response

    def stack_name(self, part: str) -> str:
        return f"CuddlyTales{self.name.capitalize()}{part}"

    @property
    def prefix(self) -> str:
        """cuddly-tales (or cuddly-tales-staging)"""
        return f"cuddly-tales{f'-{self.name}' if self.name else ''}"

    def secret_name(self, part: str) -> str:
        """e.g. cuddly-tales/claude-api-key"""
        return f"{self.prefix}/{part}"


# Public, but kept out of search results: it's a demo for reviewers, and every
# visit can spend on the LLM (within the daily story cap).
LIVE = Stage(name="", site_domain=f"cuddly-tales.{ZONE_NAME}", search_engines=False)
