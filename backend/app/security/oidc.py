"""Provider-neutral discovery with an optional private backchannel origin."""

from urllib.parse import urlsplit, urlunsplit

from authlib.integrations.starlette_client import StarletteOAuth2App


class OIDCClient(StarletteOAuth2App):
    def __init__(self, *args, public_issuer, internal_origin=None, **kwargs):
        self.public_issuer = public_issuer
        self.internal_origin = internal_origin
        super().__init__(*args, **kwargs)

    async def load_server_metadata(self):
        metadata = await super().load_server_metadata()
        if metadata.get("issuer") != self.public_issuer:
            raise ValueError("Identity discovery issuer does not match configuration")
        if self.internal_origin:
            public = urlsplit(self.public_issuer)
            internal = urlsplit(self.internal_origin)
            for name in ("token_endpoint", "jwks_uri", "userinfo_endpoint"):
                if name not in metadata:
                    continue
                endpoint = urlsplit(metadata[name])
                if (endpoint.scheme, endpoint.netloc) == (public.scheme, public.netloc):
                    metadata[name] = urlunsplit(
                        (internal.scheme, internal.netloc, endpoint.path, endpoint.query, "")
                    )
        return metadata
