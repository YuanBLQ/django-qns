# Django QiNiu Cloud Storage
add qiniu cloud support for Django

## install
```
pip install django-qns
```

## usage
change the default storage to django-qns:
```
STATICFILES_STORAGE = 'storage.backends.qiniu_storage.QiNiuStorage'
```
or
```
DEFAULT_FILE_STORAGE = 'storage.backends.qiniu_storage.QiNiuStorage'
```

add configure to the django-qns in `settings.py`:
```
QINIU_STORAGE = {
    'access_key': 'ak',
    'secret_key': 'sk',
    'bucket_name': 'your bucket name',
    'domain': 'http://example.com',
    'prefix': 'some-prefix'
}
```
