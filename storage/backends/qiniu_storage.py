import posixpath
from django.conf import settings
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property
from django.core.files.storage import Storage
from django.core.files.base import File
from django.core.exceptions import SuspiciousOperation
from qiniu import Auth, put_data, BucketManager
from .utils import QiNiuError, safe_join
from urllib.parse import urljoin
import requests
import io
import os


@deconstructible
class QiNiuStorage(Storage):

    def __init__(self, options=None):
        if not options:
            options = settings.QINIU_STORAGE
        self.access_key = options.get('access_key')
        self.secret_key = options.get('secret_key')
        self.bucket_name = options.get('bucket_name')
        self.domain = options.get('domain')
        self.prefix = options.get('prefix', '')
        self.auth = Auth(self.access_key, self.secret_key)

    def _open(self, name, mode='rb'):
        """Called by Storage.open() return a File object"""
        name = self._clean_name(name)
        return QiNiuFile(name, self.bucket_name, self.domain, self.access_key, self.secret_key, mode)

    def _save(self, name, content):
        """3. Called by Storage.save()
        The name will already have gone through get_valid_name() and get_available_name()
        content: <django.core.files.uploadedfile.InMemoryUploadedFile>
        return the key of the file in bucket
        """
        if hasattr(content, 'chunks'):
            data = b''.join(chunk for chunk in content.chunks())
        else:
            data = content.read()

        return self._put_data(name, data)

    def get_valid_name(self, name):
        """1. return a filename suitable for use with the underlying storage system
        name: the original filename
              if upload_to is a callable, the filename returned by that method after any path information is **removed**
        """
        clean_name = self._clean_name(name)
        return clean_name

    def get_available_name(self, name, max_length=None):
        """2. a filename that is available in the storage mechanism
        name:  already cleaned to a filename valid for the storage system
               if upload_to, path information is **added**
        """
        clean_name = self._clean_name(name)
        return clean_name

    def _clean_qiniu_cache_file(self):
        cache_file = os.path.join(settings.BASE_DIR, '.qiniu_pythonsdk_hostscache.json')
        if os.path.exists(cache_file):
            os.remove(cache_file)

    def _put_data(self, name, data):
        """upload data to qiniu cloud"""
        name = self._normalize_name(self._clean_name(name))
        token = self.auth.upload_token(self.bucket_name, name)
        ret, info = put_data(token, name, data)
        if ret is None or ret['key'] != name:
            raise QiNiuError(info)
        print(f'{name} ... ok')
        self._clean_qiniu_cache_file()
        return name

    def _clean_name(self, name):
        """
        Cleans the name so that Windows style paths work
        """
        # Normalize Windows style paths
        clean_name = posixpath.normpath(name).replace('\\', '/')

        # os.path.normpath() can strip trailing slashes so we implement
        # a workaround here.
        if name.endswith('/') and not clean_name.endswith('/'):
            # Add a trailing slash as it was stripped.
            clean_name += '/'
        return clean_name

    def _normalize_name(self, name):
        """
        Normalizes the name so that paths like /path/to/ignored/../something.txt
        work. We check to make sure that the path pointed to is not outside
        the directory specified by the LOCATION setting.
        """
        try:
            return safe_join(self.prefix, name)
        except ValueError:
            raise SuspiciousOperation("Attempted access to '%s' denied." % name)

    def _file_stat(self, name):
        bucket = BucketManager(self.auth)
        ret, info = bucket.stat(self.bucket_name, name)
        if ret is None:
            raise QiNiuError(info)
        self.file_stat = ret
        return ret

    def path(self, name):
        """if your class provides local file storage, it must be override"""
        return name

    def delete(self, name):
        pass

    def exists(self, name):
        try:
            name = self._normalize_name(self._clean_name(name))
            self._file_stat(name)
            return True
        except QiNiuError:
            return False

    def listdir(self, path):
        pass

    def size(self, name):
        """unit：Byte"""
        name = self._normalize_name(self._clean_name(name))
        file_stat = self._file_stat(name)
        return file_stat.get('fsize', 0)

    def url(self, name):
        return urljoin(self.domain, name)

    def get_accessed_time(self, name):
        return self.get_modified_time(name)

    def get_created_time(self, name):
        return self.get_modified_time(name)

    def get_modified_time(self, name):
        name = self._normalize_name(self._clean_name(name))
        file_stat = self._file_stat(name)
        timestamp = int(file_stat.get('putTime'))
        return timezone.make_aware(timezone.datetime.fromtimestamp(timestamp / 10000000))


@deconstructible
class QiNiuFile(File):
    def __init__(self, name, bucket_name, domain, access_key, secret_key, mode='rb'):
        self.name = name
        self.mode = mode
        self.bucket_name = bucket_name
        self.domain = domain
        self.access_key = access_key
        self.secret_key = secret_key
        self.auth = Auth(self.access_key, self.secret_key)
        self.file = None

        if 'w' in mode or 'a' in mode:
            raise ValueError('qi niu file can only read.')
        if 'r' in mode and ('w' in mode or 'a' in mode):
            raise ValueError('qi niu file cannot read and write in the same time.')

    def _get_file(self):
        if self._file is None:
            data = self._read()
            self._file = io.BytesIO(data)
        return self._file

    def _set_file(self, value):
        self._file = value

    file = property(_get_file, _set_file)

    def _read(self):
        url = urljoin(self.domain, self.name)
        private_url = self.auth.private_download_url(url)
        r = requests.get(private_url)
        if r.status_code == 200:
            return r.content
        return b''

    def __len__(self):
        bucket = BucketManager(self.auth)
        ret, info = bucket.stat(self.bucket_name, self.name)
        if ret is None:
            raise QiNiuError(info)
        return ret.get('fsize', 0)

    @cached_property
    def size(self):
        bucket = BucketManager(self.auth)
        ret, info = bucket.stat(self.bucket_name, self.name)
        if ret is None:
            raise QiNiuError(info)
        return ret.get('fsize', 0)

    def read(self, num_bytes=None):
        return self.file.read(num_bytes)

    def close(self):
        self.file.close()
