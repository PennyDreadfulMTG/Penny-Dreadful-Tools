import binascii
import datetime
import functools
import os
from typing import Any, Callable, Dict, List

from flask import make_response, request
from werkzeug.contrib.cache import SimpleCache

from decksite import get_season_id
from magic import rotation
from shared_web import localization

CACHE = SimpleCache() # type: ignore

def cached() -> Callable:
    return cached_impl(cacheable=True, must_revalidate=True, client_only=False, client_timeout=1 * 60 * 60, server_timeout=5 * 60)

# pylint: disable=too-many-arguments
def cached_impl(cacheable: bool = False,
                must_revalidate: bool = True,
                client_only: bool = True,
                client_timeout: int = 0,
                server_timeout: int = 5 * 60,
                key: str = 'view{id}{locale}') -> Callable:
    """
    @see https://jakearchibald.com/2016/caching-best-practices/
         https://developers.google.com/web/fundamentals/performance/optimizing-content-efficiency/http-caching
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def decorated_function(*args: List[Any], **kwargs: Dict[str, Any]) -> Callable:
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

                actual_client_timeout = client_timeout
                actual_server_timeout = server_timeout
                if get_season_id() and get_season_id() != 'all' and get_season_id() < rotation.current_season_num():
                    actual_client_timeout = 7 * 24 * 60 * 60
                    actual_server_timeout = 7 * 24 * 60 * 60

                cache_policy += ', max-age={client_timeout}'.format(client_timeout=actual_client_timeout)

            headers = {}
            cache_policy = cache_policy.strip(',')
            headers['Cache-Control'] = cache_policy
            now = datetime.datetime.utcnow()

            client_etag = request.headers.get('If-None-Match')

            response = CACHE.get(cache_key)  # type: ignore
            # Respect a hard refresh from the client, if sent.
            # Note: Safari/OSX does not send a Cache-Control (or any additional) header on a hard refresh so people using Safari can't bypass/refresh server cache.
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
                    CACHE.set(cache_key, response, timeout=actual_server_timeout)

            response.headers.extend(headers)
            return response
        return decorated_function
    return decorator
