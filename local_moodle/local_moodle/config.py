import uuid


class Config:
    #SECRET_KEY = uuid.uuid4().hex
    SECRET_KEY = '2893b6e6bdd540afaca7d18dbc62568e'
    SQLALCHEMY_DATABASE_URI = "sqlite:///../instance/app.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
