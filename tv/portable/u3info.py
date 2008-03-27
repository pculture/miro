
from os import getenv
import os.path

app_data_path = getenv("U3_APP_DATA_PATH")
if app_data_path:
    app_data_path = os.path.normcase(app_data_path)
device_document_path = getenv("U3_DEVICE_DOCUMENT_PATH")
if device_document_path:
    device_document_path = os.path.normcase(device_document_path)

u3_active = app_data_path is not None and device_document_path is not None and os.path.isdir(app_data_path) and os.path.isdir(device_document_path)

app_data_prefix = u"$APP_DATA_PATH"
device_document_prefix = u"$DEVICE_DOCUMENT_PATH"
