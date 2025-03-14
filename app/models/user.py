from datetime import datetime

from flask import current_app
from flask_login import AnonymousUserMixin, UserMixin
from itsdangerous import URLSafeTimedSerializer as Serializer
from itsdangerous import BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db, login_manager

from .observation import ObservingSession
from .chart_theme import ChartTheme


class Permission:
    GENERAL = 0x01
    EDIT_COMMON_CONTENT = 0x10
    ADMINISTER = 0xff


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    index = db.Column(db.String(64))
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    _role_id_map = None

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.GENERAL, 'main', True),
            'Editor': (Permission.EDIT_COMMON_CONTENT or Permission.GENERAL, 'main', False),
            'Administrator': (
                Permission.ADMINISTER,
                'admin',
                False  # grants all permissions
            )
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.index = roles[r][1]
            role.default = roles[r][2]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role \'%s\'>' % self.name


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(64), unique=True, index=True)
    confirmed = db.Column(db.Boolean, default=False)
    full_name = db.Column(db.String(265), index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    create_date = db.Column(db.DateTime, default=datetime.now())
    last_login_date = db.Column(db.DateTime)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    lang_code = db.Column(db.String(2))
    country_code = db.Column(db.String(2))
    is_hidden = db.Column(db.Boolean, default=False)
    is_disabled = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    git_repository = db.Column(db.String(512))
    git_ssh_public_key = db.Column(db.Text)
    git_ssh_private_key = db.Column(db.Text)
    git_content_repository = db.Column(db.String(512))
    git_content_ssh_public_key = db.Column(db.Text)
    git_content_ssh_private_key = db.Column(db.Text)

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['ADMIN_EMAIL']:
                self.role = Role.query.filter_by(
                    permissions=Permission.ADMINISTER).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()

    @property
    def is_active(self):
        return not self.is_disabled and not self.is_deleted

    def can(self, permissions):
        return self.role is not None and \
            (self.role.permissions & permissions) == permissions

    def is_admin(self):
        return self.can(Permission.ADMINISTER)

    def is_editor(self):
        return self.can(Permission.EDIT_COMMON_CONTENT)

    @property
    def password(self):
        raise AttributeError('`password` is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self):
        """Generate a confirmation token to email a new user."""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'confirm': self.id})

    def generate_email_change_token(self, new_email):
        """Generate an email change token to email an existing user."""
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'change_email': self.id, 'new_email': new_email}, b"czsky")

    def generate_password_reset_token(self):
        """
        Generate a password reset change token to email to an existing user.
        """
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'reset': self.id}, b"czsky")

    def confirm_account(self, token, expiration=604800):
        """Verify that the provided token is for this user's id."""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expiration)
        except (BadSignature, SignatureExpired):
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        db.session.commit()
        return True

    def change_email(self, token, expiration=3600):
        """Verify the new email for this user."""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expiration)
        except (BadSignature, SignatureExpired):
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        db.session.add(self)
        db.session.commit()
        return True

    def reset_password(self, token, new_password, expiration=3600):
        """Verify the new password for this user."""
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expiration)
        except (BadSignature, SignatureExpired):
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        db.session.commit()
        return True

    def get_first_name(self):
        spl = self.full_name.rsplit(' ', 1)
        return spl[0] if len(spl) > 1 else ''

    def get_last_name(self):
        spl = self.full_name.rsplit(' ', 1)
        return spl[1] if len(spl) > 1 else spl[0]

    @property
    def user_themes(self):
        custom_themes = (
            ChartTheme.query
            .filter_by(user_id=self.id, is_active=True)
            .order_by(ChartTheme.order)
            .limit(5)
            .all()
        )
        return custom_themes

    @property
    def active_observing_session(self):
        session = ObservingSession.query.filter_by(user_id=self.id, is_active=True).first()
        return session

    @staticmethod
    def generate_fake(count=100, **kwargs):
        """Generate a number of fake users for testing."""
        from sqlalchemy.exc import IntegrityError
        from random import seed, choice
        from faker import Faker

        fake = Faker()
        roles = Role.query.all()

        seed()
        for i in range(count):
            u = User(
                user_name=fake.user_name(),
                full_name=fake.full_name(),
                email=fake.email(),
                password='password',
                confirmed=True,
                role=choice(roles),
                **kwargs)
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    @staticmethod
    def get_editor_user():
        return User.query.filter_by(user_name=current_app.config.get('EDITOR_USER_NAME_CS')).first()

    def __repr__(self):
        return '<User \'%s\'>' % self.full_name


class AnonymousUser(AnonymousUserMixin):
    def can(self, _):
        return False

    def is_admin(self):
        return False

    def is_editor(self):
        return False


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
