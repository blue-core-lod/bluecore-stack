import paramiko

_orig_auth_gss = paramiko.Transport.auth_gssapi_with_mic

def auth_gss_then_duo(self, username, gss_host, gss_deleg_creds):
    """
    Monkeypatch paramiko.Transport.auth_gssapi_with_mic function so that Duo 
    2FA works when deployed from local computer.
    """
    remaining = _orig_auth_gss(self, username, gss_host, gss_deleg_creds)

    if "keyboard-interactive" in (remaining or []):
        def duo_handler(title, instructions, prompts):
            if instructions:
                print(instructions)
            responses = []
            for prompt_text, echo in prompts:
                responses.append(input(prompt_text))
            return responses

        remaining = self.auth_interactive(username, duo_handler)

    return remaining
