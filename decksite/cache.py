import binascii
import datetime
import functools
import os

from flask import make_response, request
from werkzeug.contrib.cache import SimpleCache

from . import localization

CACHE = SimpleCache()

def cached():
    return cached_impl(cacheable=True, must_revalidate=True, client_only=False, client_timeout=1 * 60 * 60, server_timeout=5 * 60)

# pylint: disable=too-many-arguments
def cached_impl(cacheable=False, must_revalidate=True, client_only=True, client_timeout=0, server_timeout=5 * 60, key='view{id}{locale}'):
    """

    @see https://jakearchibald.com/2016/caching-best-practices/
        https://developers.google.com/web/fundamentals/performance/optimizing-content-efficiency/http-caching
    """
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = key.format(id=request.full_path, locale=localization.get_locale()) # include querystring
            cache_policy = ''
            if not cacheable:
                cache_policy += ', no-store' # tells the browser not to cache at all
            else:
                if must_revalidate: # this looks contradicting if you haven't read the article.
                    # no-cache doesn't mean "don't cache", it means it must check
                    # (or "revalidate" as it calls it) with the server before
                    # using the cached resource
                    cache_policy += ', no-cache'
                else:
                    # Also must-revalidate doesn't mean "must revalidate", it
                    # means the local resource can be used if it's younger than
                    # the provided max-age, otherwise it must revalidate
                    cache_policy += ', must-revalidate'

                if client_only:
                    cache_policy += ', private'
                else:
                    cache_policy += ', public'

                cache_policy += ', max-age={client_timeout}'.format(client_timeout=client_timeout)

            headers = {}
            cache_policy = cache_policy.strip(',')
            headers['Cache-Control'] = cache_policy
            now = datetime.datetime.utcnow()

            client_etag = request.headers.get('If-None-Match')

            response = CACHE.get(cache_key)
            # respect the hard-refresh
            if response is not None and request.headers.get('Cache-Control', '') != 'no-cache':
                headers['X-Cache'] = 'HIT from Server'
                cached_etag = response.headers.get('ETag')
                if client_etag and cached_etag and client_etag == cached_etag:
                    headers['X-Cache'] = 'HIT from Client'
                    headers['X-Last-Modified'] = response.headers.get('X-LastModified')
                    response = make_response('', 304)
            else:
                response = make_response(f(*args, **kwargs))
                if response.status_code == 200 and request.method in ['GET', 'HEAD']:
                    headers['X-Cache'] = 'MISS'
                    # - Added the headers to the response object instead of the
                    # headers dict so they get cached too
                    # - If you can find any faster random algorithm go for it.
                    response.headers.add('ETag', binascii.hexlify(os.urandom(4)))
                    response.headers.add('X-Last-Modified', str(now))
                    CACHE.set(cache_key, response, timeout=server_timeout)

            response.headers.extend(headers)
            return response
        return decorated_function
    return decorator
