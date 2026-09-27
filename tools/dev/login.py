"""Signs in through Keycloak's browser flow (auth code + PKCE) and prints the access token."""
import base64, hashlib, html, http.cookiejar, json, re, secrets, ssl, sys, urllib.error, urllib.parse, urllib.request

KC = "https://localhost:8443/realms/aegle/protocol/openid-connect"
REDIRECT = "https://localhost:5173/"
user, password, ca = sys.argv[1], sys.argv[2], sys.argv[3]
ctx = ssl.create_default_context(cafile=ca)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None if newurl.startswith(REDIRECT) else super().redirect_request(req, fp, code, msg, headers, newurl)

opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                     urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect)
verifier = secrets.token_urlsafe(48)
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
q = urllib.parse.urlencode({"client_id": "aegle-web", "redirect_uri": REDIRECT, "response_type": "code",
                            "scope": "openid", "code_challenge": challenge, "code_challenge_method": "S256",
                            "state": secrets.token_hex(8)})
page = opener.open(f"{KC}/auth?{q}").read().decode()
action = html.unescape(re.search(r'action="([^"]+)"', page).group(1))
try:
    opener.open(action, urllib.parse.urlencode({"username": user, "password": password}).encode())
    sys.exit("login did not redirect back (bad credentials?)")
except urllib.error.HTTPError as e:
    code = urllib.parse.parse_qs(urllib.parse.urlparse(e.headers["Location"]).query)["code"][0]
tok = json.load(opener.open(f"{KC}/token", urllib.parse.urlencode({
    "grant_type": "authorization_code", "client_id": "aegle-web", "code": code,
    "redirect_uri": REDIRECT, "code_verifier": verifier}).encode()))
print(tok["access_token"])
