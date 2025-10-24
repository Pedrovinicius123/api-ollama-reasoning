from mongoengine import Document, FileField, StringField
import os.path as path

class Upload(Document):
    filename = StringField()
    file = FileField()
    meta = {'collection': 'uploads'}

def upload_file(temp_log_dir:str, filename:str, raw_file):
    new_upload_doc = Upload()
    new_upload_doc.filename = path.join(temp_log_dir, filename)
    new_upload_doc.file.put(raw_file, content_type="text/markdown")
    new_upload_doc.save()
  
