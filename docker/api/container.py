import six
import warnings

from .. import errors
from .. import utils


class ContainerApiMixin(object):
    @utils.check_resource
    def attach(self, container, stdout=True, stderr=True,
               stream=False, logs=False):
        params = {
            'logs': logs and 1 or 0,
            'stdout': stdout and 1 or 0,
            'stderr': stderr and 1 or 0,
            'stream': stream and 1 or 0,
        }
        u = self._url("/containers/{0}/attach", container)
        response = self._post(u, params=params, stream=stream)

        return self._get_result(container, stream, response)

    @utils.check_resource
    def attach_socket(self, container, params=None, ws=False):
        if params is None:
            params = {
                'stdout': 1,
                'stderr': 1,
                'stream': 1
            }

        if ws:
            return self._attach_websocket(container, params)

        u = self._url("/containers/{0}/attach", container)
        return self._get_raw_response_socket(self.post(
            u, None, params=self._attach_params(params), stream=True))

    @utils.check_resource
    def commit(self, container, repository=None, tag=None, message=None,
               author=None, conf=None):
        params = {
            'container': container,
            'repo': repository,
            'tag': tag,
            'comment': message,
            'author': author
        }
        u = self._url("/commit")
        return self._result(self._post_json(u, data=conf, params=params),
                            json=True)

    def containers(self, quiet=False, all=False, trunc=False, latest=False,
                   since=None, before=None, limit=-1, size=False,
                   filters=None):
        params = {
            'limit': 1 if latest else limit,
            'all': 1 if all else 0,
            'size': 1 if size else 0,
            'trunc_cmd': 1 if trunc else 0,
            'since': since,
            'before': before
        }
        if filters:
            params['filters'] = utils.convert_filters(filters)
        u = self._url("/containers/json")
        res = self._result(self._get(u, params=params), True)

        if quiet:
            return [{'Id': x['Id']} for x in res]
        if trunc:
            for x in res:
                x['Id'] = x['Id'][:12]
        return res

    @utils.check_resource
    def copy(self, container, resource):
        if utils.version_gte(self._version, '1.20'):
            warnings.warn(
                'Client.copy() is deprecated for API version >= 1.20, '
                'please use get_archive() instead',
                DeprecationWarning
            )
        res = self._post_json(
            self._url("/containers/{0}/copy".format(container)),
            data={"Resource": resource},
            stream=True
        )
        self._raise_for_status(res)
        return res.raw

    def create_container(self, image, command=None, hostname=None, user=None,
                         detach=False, stdin_open=False, tty=False,
                         mem_limit=None, ports=None, environment=None,
                         dns=None, volumes=None, volumes_from=None,
                         network_disabled=False, name=None, entrypoint=None,
                         cpu_shares=None, working_dir=None, domainname=None,
                         memswap_limit=None, cpuset=None, host_config=None,
                         mac_address=None, labels=None, volume_driver=None):

        if isinstance(volumes, six.string_types):
            volumes = [volumes, ]

        if host_config and utils.compare_version('1.15', self._version) < 0:
            raise errors.InvalidVersion(
                'host_config is not supported in API < 1.15'
            )

        config = self.create_container_config(
            image, command, hostname, user, detach, stdin_open,
            tty, mem_limit, ports, environment, dns, volumes, volumes_from,
            network_disabled, entrypoint, cpu_shares, working_dir, domainname,
            memswap_limit, cpuset, host_config, mac_address, labels,
            volume_driver
        )
        return self.create_container_from_config(config, name)

    def create_container_config(self, *args, **kwargs):
        return utils.create_container_config(self._version, *args, **kwargs)

    def create_container_from_config(self, config, name=None):
        u = self._url("/containers/create")
        params = {
            'name': name
        }
        res = self._post_json(u, data=config, params=params)
        return self._result(res, True)

    def create_host_config(self, *args, **kwargs):
        if not kwargs:
            kwargs = {}
        if 'version' in kwargs:
            raise TypeError(
                "create_host_config() got an unexpected "
                "keyword argument 'version'"
            )
        kwargs['version'] = self._version
        return utils.create_host_config(*args, **kwargs)

    @utils.check_resource
    def diff(self, container):
        return self._result(
            self._get(self._url("/containers/{0}/changes", container)), True
        )

    @utils.check_resource
    def export(self, container):
        res = self._get(
            self._url("/containers/{0}/export", container), stream=True
        )
        self._raise_for_status(res)
        return res.raw

    @utils.check_resource
    @utils.minimum_version('1.20')
    def get_archive(self, container, path):
        params = {
            'path': path
        }
        url = self._url('/containers/{0}/archive', container)
        res = self._get(url, params=params, stream=True)
        self._raise_for_status(res)
        encoded_stat = res.headers.get('x-docker-container-path-stat')
        return (
            res.raw,
            utils.decode_json_header(encoded_stat) if encoded_stat else None
        )

    @utils.check_resource
    def inspect_container(self, container):
        return self._result(
            self._get(self._url("/containers/{0}/json", container)), True
        )

    @utils.check_resource
    def kill(self, container, signal=None):
        url = self._url("/containers/{0}/kill", container)
        params = {}
        if signal is not None:
            params['signal'] = signal
        res = self._post(url, params=params)

        self._raise_for_status(res)

    @utils.check_resource
    def logs(self, container, stdout=True, stderr=True, stream=False,
             timestamps=False, tail='all'):
        if utils.compare_version('1.11', self._version) >= 0:
            params = {'stderr': stderr and 1 or 0,
                      'stdout': stdout and 1 or 0,
                      'timestamps': timestamps and 1 or 0,
                      'follow': stream and 1 or 0,
                      }
            if utils.compare_version('1.13', self._version) >= 0:
                if tail != 'all' and (not isinstance(tail, int) or tail <= 0):
                    tail = 'all'
                params['tail'] = tail
            url = self._url("/containers/{0}/logs", container)
            res = self._get(url, params=params, stream=stream)
            return self._get_result(container, stream, res)
        return self.attach(
            container,
            stdout=stdout,
            stderr=stderr,
            stream=stream,
            logs=True
        )

    @utils.check_resource
    def pause(self, container):
        url = self._url('/containers/{0}/pause', container)
        res = self._post(url)
        self._raise_for_status(res)

    @utils.check_resource
    def port(self, container, private_port):
        res = self._get(self._url("/containers/{0}/json", container))
        self._raise_for_status(res)
        json_ = res.json()
        private_port = str(private_port)
        h_ports = None

        # Port settings is None when the container is running with
        # network_mode=host.
        port_settings = json_.get('NetworkSettings', {}).get('Ports')
        if port_settings is None:
            return None

        if '/' in private_port:
            return port_settings.get(private_port)

        h_ports = port_settings.get(private_port + '/tcp')
        if h_ports is None:
            h_ports = port_settings.get(private_port + '/udp')

        return h_ports

    @utils.check_resource
    @utils.minimum_version('1.20')
    def put_archive(self, container, path, data):
        params = {'path': path}
        url = self._url('/containers/{0}/archive', container)
        res = self._put(url, params=params, data=data)
        self._raise_for_status(res)
        return res.status_code == 200

    @utils.check_resource
    def remove_container(self, container, v=False, link=False, force=False):
        params = {'v': v, 'link': link, 'force': force}
        res = self._delete(
            self._url("/containers/{0}", container), params=params
        )
        self._raise_for_status(res)

    @utils.minimum_version('1.17')
    @utils.check_resource
    def rename(self, container, name):
        url = self._url("/containers/{0}/rename", container)
        params = {'name': name}
        res = self._post(url, params=params)
        self._raise_for_status(res)

    @utils.check_resource
    def resize(self, container, height, width):
        params = {'h': height, 'w': width}
        url = self._url("/containers/{0}/resize", container)
        res = self._post(url, params=params)
        self._raise_for_status(res)

    @utils.check_resource
    def restart(self, container, timeout=10):
        params = {'t': timeout}
        url = self._url("/containers/{0}/restart", container)
        res = self._post(url, params=params)
        self._raise_for_status(res)

    @utils.check_resource
    def start(self, container, *args, **kwargs):
        if args or kwargs:
            raise errors.DeprecatedMethod(
                'Providing configuration in the start() method is no longer '
                'supported. Use the host_config param in create_container '
                'instead.'
            )
        url = self._url("/containers/{0}/start", container)
        res = self._post(url)
        self._raise_for_status(res)

    @utils.minimum_version('1.17')
    @utils.check_resource
    def stats(self, container, decode=None):
        url = self._url("/containers/{0}/stats", container)
        return self._stream_helper(self._get(url, stream=True), decode=decode)

    @utils.check_resource
    def stop(self, container, timeout=10):
        params = {'t': timeout}
        url = self._url("/containers/{0}/stop", container)

        res = self._post(url, params=params,
                         timeout=(timeout + (self.timeout or 0)))
        self._raise_for_status(res)

    @utils.check_resource
    def top(self, container, ps_args=None):
        u = self._url("/containers/{0}/top", container)
        params = {}
        if ps_args is not None:
            params['ps_args'] = ps_args
        return self._result(self._get(u, params=params), True)

    @utils.check_resource
    def unpause(self, container):
        url = self._url('/containers/{0}/unpause', container)
        res = self._post(url)
        self._raise_for_status(res)

    @utils.check_resource
    def wait(self, container, timeout=None):
        url = self._url("/containers/{0}/wait", container)
        res = self._post(url, timeout=timeout)
        self._raise_for_status(res)
        json_ = res.json()
        if 'StatusCode' in json_:
            return json_['StatusCode']
        return -1
