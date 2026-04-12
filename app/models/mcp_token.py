from datetime import datetime

from .. import db


class McpUserToken(db.Model):
    __tablename__ = "mcp_user_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_id = db.Column(db.String(32), nullable=False, unique=True, index=True)
    token_name = db.Column(db.String(128), nullable=False)
    token_prefix = db.Column(db.String(16), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    scope = db.Column(db.String(256), nullable=False, default="wishlist:read")
    last_used_date = db.Column(db.DateTime, nullable=True)
    expires_date = db.Column(db.DateTime, nullable=True)
    is_revoked = db.Column(db.Boolean, nullable=False, default=False)
    create_date = db.Column(db.DateTime, default=datetime.now())
    update_date = db.Column(db.DateTime, default=datetime.now())

    def __repr__(self):
        return f"<McpUserToken '{self.token_id}'>"
