from datetime import datetime

from .. import db


class McpOAuthClient(db.Model):
    __tablename__ = "mcp_oauth_clients"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    client_name = db.Column(db.String(128), nullable=True)
    client_secret_hash = db.Column(db.String(255), nullable=True)
    token_endpoint_auth_method = db.Column(db.String(32), nullable=False, default="none")
    redirect_uris = db.Column(db.Text, nullable=False)
    scope = db.Column(db.String(256), nullable=True)
    create_date = db.Column(db.DateTime, default=datetime.now)
    last_used_date = db.Column(db.DateTime, nullable=True)

    def redirect_uri_list(self):
        return [uri for uri in (self.redirect_uris or "").split("\n") if uri]

    def __repr__(self):
        return f"<McpOAuthClient '{self.client_id}'>"


class McpOAuthAuthorizationCode(db.Model):
    __tablename__ = "mcp_oauth_authorization_codes"

    id = db.Column(db.Integer, primary_key=True)
    code_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    client_id = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    redirect_uri = db.Column(db.String(512), nullable=False)
    scope = db.Column(db.String(256), nullable=False)
    code_challenge = db.Column(db.String(128), nullable=False)
    resource = db.Column(db.String(512), nullable=True)
    expires_date = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, nullable=False, default=False)
    token_row_id = db.Column(db.Integer, nullable=True)
    create_date = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<McpOAuthAuthorizationCode '{self.id}'>"


class McpOAuthRefreshTokenHistory(db.Model):
    """SHA-256 hashes of rotated-out refresh tokens, to detect their replay."""
    __tablename__ = "mcp_oauth_refresh_token_history"

    id = db.Column(db.Integer, primary_key=True)
    token_row_id = db.Column(db.Integer, db.ForeignKey("mcp_user_tokens.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    create_date = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f"<McpOAuthRefreshTokenHistory '{self.id}'>"
