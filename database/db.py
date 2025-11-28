from flask_mongoengine import MongoEngine
from mongoengine import Document, FileField, StringField, IntField, ReferenceField, DoesNotExist
from werkzeug.security import generate_password_hash, check_password_hash
import os.path as path
import time

db = MongoEngine()

class User(Document):
    id = IntField(primary_key=True)
    username = StringField(required=True, unique=True)
    email = StringField(required=True, unique=True)
    password_hash = StringField(required=True)

    def generate_password_hash(self, new_password):
        # store a salted hash using werkzeug
        if isinstance(new_password, bytes):
            new_password = new_password.decode('utf-8')
        self.password_hash = generate_password_hash(new_password)

    def check_password(self, password):
        if not getattr(self, 'password_hash', None):
            return False
        return check_password_hash(self.password_hash, password)

class Upload(Document):
    creator = ReferenceField(User)
    id = IntField(primary_key=True)
    depth=IntField(default=0)
    filename = StringField(required=True)
    file = FileField(required=True)
    meta = {'collection': 'uploads'}


def upload_file(user:User, log_dir:str, filename:str, raw_file, initial:bool=False):
    try:
        existing = Upload.objects(filename=path.join(log_dir, filename), creator=user).first()

    except Exception as err:
        print(f"File does not exist, creating new upload: {err}")
        new_upload_doc = Upload(id=Upload.objects.count()+1, creator=user)
        new_upload_doc.filename = path.join(log_dir, filename)
        new_upload_doc.file.put(raw_file, content_type="text/markdown")
        new_upload_doc.save()

        return new_upload_doc

    else:
        content = b" "
        if not initial:
            print("Updating existing file...")
            content = existing.file.read() if existing and existing.file.read() else b" "
            existing.file.delete()
        
        existing.file.replace(content + raw_file, content_type="text/markdown")
        existing.save()

        return existing
