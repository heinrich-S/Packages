# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha_api
import keypirinha as kp
import keypirinha_util as kpu
import codecs
import hashlib
import json
import os
import shlex
import secrets
import traceback
import urllib.parse
import uuid
import zlib

def i2xx(b, prefix):
    if not isinstance(b, int): raise TypeError
    x = hex(b)[2:]
    while (len(x) % 2): x = "0" + x
    if prefix: x = "0x" + x
    return x

class _Functor:
    __slots__ = ("name", "label", "desc")

    def __init__(self, name, label, desc):
        self.name = name
        self.label = label
        self.desc = desc

    def convert(self, data):
        raise NotImplementedError

class _Functor_ArgQuoteUnix(_Functor):
    def __init__(self):
        super().__init__("arg_quote_unix", "Arg Quote (Unix-style)",
                         "Quote a command line argument (Unix-style)")

    def convert(self, data):
        return (shlex.quote(data), )

class _Functor_ArgQuoteWin(_Functor):
    def __init__(self):
        super().__init__("arg_quote_win", "Arg Quote (Windows-style)",
                         "Quote a command line argument (Windows-style)")

    def convert(self, data):
        return (kpu.cmdline_quote(data), )

class _Functor_ArgSplitUnix(_Functor):
    def __init__(self):
        super().__init__("arg_split_unix", "Arg Split (Unix-style)",
                         "Split a command line (Unix-style)")

    def convert(self, data):
        return shlex.split(data)

class _Functor_ArgSplitWin(_Functor):
    def __init__(self):
        super().__init__("arg_split_win", "Arg Split (Windows-style)",
                         "Split a command line (Windows-style)")

    def convert(self, data):
        return kpu.cmdline_split(data)

class _Functor_Keypirinha(_Functor):
    def __init__(self):
        super().__init__("keypirinha", "Hash (Keypirinha)",
                         "Hash a string with Keypirinha's internal hasher")

    def convert(self, data):
        if not data: return ()
        result = keypirinha_api.hash_string(data)
        return (i2xx(result, False), i2xx(result, True), str(result))

class _Functor_Hashlib(_Functor):
    __slots__ = ("algo")

    def __init__(self, algo):
        self.algo = algo
        super().__init__(algo.lower(), "Hash (" + algo.lower() + ")",
                         "Hash a string with the " + algo + " algorithm")

    def convert(self, data):
        if isinstance(data, str):
            data = data.encode(encoding="utf-8", errors="strict")
        hasher = hashlib.new(self.algo)
        hasher.update(data)
        result = hasher.hexdigest()
        return (result.lower(), result.upper())

class _Functor_RandBytes(_Functor):
    def __init__(self):
        super().__init__("rand_bytes", "Random Bytes",
                         "Generate a string of random bytes")

    def convert(self, data):
        # data arg is interpreted as the desired count of bytes to generate
        try:
            if not isinstance(data, int):
                data = int(data, base=10)
        except:
            data = 8

        randbytes = os.urandom(data)
        return (
            randbytes.hex(),
            " ".join([i2xx(b, False) for b in randbytes]),
            " ".join([i2xx(b, True) for b in randbytes]))

class _Functor_RandPassword(_Functor):
    def __init__(self):
        super().__init__("rand_password", "Random Password",
                         "Generate a random password")

    def convert(self, data):
        # data arg is interpreted as the desired count of characters to generate
        if not isinstance(data, int):
            try:
                data = int(data, base=10)
            except:
                data = 8
        if not data:
            return ()

        # value returned by secrets.token_urlsafe is base64-encoded so longer
        # than requested
        return (secrets.token_urlsafe(data)[0:data], )

class _Functor_RandUUID(_Functor):
    def __init__(self):
        super().__init__("rand_uuid", "Random UUID/GUID",
                         "Generate a random UUID/GUID")

    def convert(self, data=None):
        obj = uuid.uuid4()
        return (
            str(obj),                     # 4ef6af2f-3f48-4b30-9361-93fee889d94d
            "{" + str(obj) + "}",         # {4ef6af2f-3f48-4b30-9361-93fee889d94d}
            "{" + str(obj).upper() + "}", # {4EF6AF2F-3F48-4B30-9361-93FEE889D94D}
            obj.hex,                      # 4ef6af2f3f484b30936193fee889d94d
            obj.urn,                      # urn:uuid:4ef6af2f-3f48-4b30-9361-93fee889d94d
            str(obj.int))                 # 104960641863412236247170365975433959757

class _Functor_Rot13(_Functor):
    def __init__(self):
        super().__init__("rot13", "rot13",
                         "rot13 a string (similar to PHP's str_rot13)")

    def convert(self, data):
        # reminder: rot_13 codec is text-to-text
        return (codecs.encode(data, encoding="rot_13", errors="strict"), )


class _Functor_UrlQuote(_Functor):
    def __init__(self):
        super().__init__("url_quote", "URL Quote",
                         "URL-quote a string (including space chars)")

    def convert(self, data):
        return (urllib.parse.quote(data), )

class _Functor_UrlQuotePlus(_Functor):
    def __init__(self):
        super().__init__("url_quote_plus", "URL Quote+",
                         "URL-quote+ a string (space chars to +)")

    def convert(self, data):
        return (urllib.parse.quote_plus(data), )

class _Functor_UrlSplit(_Functor):
    def __init__(self):
        super().__init__("url_split", "URL Split", "Split a URL")

    def convert(self, data):
        # test: https://l0gin:p%4055w0rd@www.example.com:443/%7Ebob/index.html?arg=%20val;a2=test#specific-section
        url = urllib.parse.urlsplit(data)
        unquoted_results = []
        raw_results = []
        for k in ("username", "password", "hostname", "path", "query",
                  "fragment", "port", "scheme", "netloc", "port"):
            v = getattr(url, k)
            if not v: continue

            desc = k + " - press Enter to copy"

            if k == "query":
                unquoted_results.append({
                    'label': v,
                    'target': v,
                    'desc': desc})
                try:
                    json_args = json.dumps(urllib.parse.parse_qs(v))
                    unquoted_results.append({
                        'label': json_args,
                        'target': json_args,
                        'desc': "json " + desc})
                except ValueError:
                    pass
            else:
                v = str(v)
                uv = urllib.parse.unquote(v)

                if uv and uv != v:
                    unquoted_results.append({
                        'label': uv,
                        'target': uv,
                        'desc': desc})
                    raw_results.append({
                        'label': v,
                        'target': v,
                        'desc': "raw " + desc})
                else:
                    unquoted_results.append({
                        'label': v,
                        'target': v,
                        'desc': desc})

        return unquoted_results + raw_results

class _Functor_UrlUnquote(_Functor):
    def __init__(self):
        super().__init__("url_unquote_plus", "URL Unquote",
                         "URL-unquote a string")

    def convert(self, data):
        return (urllib.parse.unquote_plus(data), )

class _Functor_ZLib(_Functor):
    def __init__(self, func_name):
        super().__init__(func_name, "Hash (" + func_name.lower() + ")",
                         "Hash a string with the " + func_name + " algorithm")

    def convert(self, data):
        if isinstance(data, str):
            data = data.encode(encoding="utf-8", errors="strict")
        result = getattr(zlib, self.name)(data)
        return (i2xx(result, False), i2xx(result, True), str(result))

class _Functor_ChangeCase(_Functor):
    _algorithms = ("upper", "lower", "capitalize", "title")

    def __init__(self):
        super().__init__("change_case", "Cases", "Change the case to a specific type")

    def convert(self, data):
        data = data.strip() if isinstance(data, str) else str(data)

        results = []
        for algo in self._algorithms:
            desc = "Change to {} case".format(algo)
            value = getattr(data, algo)()
            results.append({'label': value, 'target': value, 'desc': desc})
        return results


class String(kp.Plugin):
    """
    A multi-purpose plugin for string conversion and generation

    Features:
    * hash a string using standard algorithms like CRC32, MD5, SHA*, etc...
    * generate a random UUID, also called GUID
    * generate a random password
    * generate random bytes
    * URL-quote a string
    * URL-unquote a string
    * split a URL
    * convert URL arguments to JSON
    * quote a command line argument (Windows & Unix style)
    * split a command line (Windows & Unix style)
    """

    ITEM_LABEL_PREFIX = "String: "
    ITEMCAT_RESULT = kp.ItemCategory.USER_BASE + 1

    functors = {}

    def __init__(self):
        super().__init__()

    def on_start(self):
        functors_list = [
            _Functor_ArgQuoteUnix(),
            _Functor_ArgQuoteWin(),
            _Functor_ArgSplitUnix(),
            _Functor_ArgSplitWin(),
            _Functor_Keypirinha(),
            _Functor_RandBytes(),
            _Functor_RandPassword(),
            _Functor_RandUUID(),
            _Functor_Rot13(),
            _Functor_UrlQuote(),
            _Functor_UrlQuotePlus(),
            _Functor_UrlSplit(),
            _Functor_UrlUnquote(),
            _Functor_ZLib("adler32"),
            _Functor_ZLib("crc32"),
            _Functor_ChangeCase()]

        for algo in hashlib.algorithms_available:
            # some algorithms are declared twice in the list, like 'MD4' and
            # 'md4', in which case we favor uppercased one
            if algo.upper() != algo and algo.upper() in hashlib.algorithms_available:
                continue
            functors_list.append(_Functor_Hashlib(algo))

        self.functors = {}
        for functor in functors_list:
            if functor.name in self.functors:
                self.warn("functor declared twice:", functor.name)
            else:
                self.functors[functor.name] = functor

    def on_catalog(self):
        catalog = []

        for name, functor in self.functors.items():
            catalog.append(self.create_item(
                category=kp.ItemCategory.REFERENCE,
                label=self.ITEM_LABEL_PREFIX + functor.label,
                short_desc=functor.desc,
                target=functor.name,
                args_hint=kp.ItemArgsHint.REQUIRED,
                hit_hint=kp.ItemHitHint.NOARGS))

        self.set_catalog(catalog)

    def on_suggest(self, user_input, items_chain):
        if not items_chain:
            return

        current_item = items_chain[-1]
        if current_item.category() != kp.ItemCategory.REFERENCE:
            return

        if current_item.target() in self.functors:
            functor = self.functors[current_item.target()]
            suggestions = []

            try:
                results = functor.convert(user_input)
                for res in results:
                    if isinstance(res, dict):
                        pass
                    else: # str
                        target = res
                        res = {'label': target, 'target': target}

                    if not res['target']:
                        continue
                    if 'desc' not in res:
                        res['desc'] = "Press Enter to copy"

                    suggestions.append(self.create_item(
                        category=self.ITEMCAT_RESULT,
                        label=res['label'],
                        short_desc=res['desc'],
                        target=res['target'],
                        args_hint=kp.ItemArgsHint.FORBIDDEN,
                        hit_hint=kp.ItemHitHint.IGNORE))

            except Exception as exc:
                traceback.print_exc()
                suggestions.append(self.create_error_item(
                    label=user_input,
                    short_desc="Error({}): {}".format(functor.name, exc)))

            self.set_suggestions(suggestions, kp.Match.ANY, kp.Sort.NONE)

        else:
            self.set_suggestions(
                self.create_error_item(
                    label=user_input,
                    short_desc="Error: unknown functor: " + current_item.target()),
                kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        if item and item.category() == self.ITEMCAT_RESULT:
            kpu.set_clipboard(item.target())
