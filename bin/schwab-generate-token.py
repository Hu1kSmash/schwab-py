#!/usr/bin/env python
import argparse
import atexit
import sys

import schwab

def main(api_key, app_secret, callback_url, token_path, requested_browser):
    try:
        schwab.auth.client_from_login_flow(
                api_key, app_secret, callback_url, token_path,
                requested_browser=requested_browser, callback_timeout=300)
        return 0
    except ImportError as exc:
        # Printed, then fall through to the manual flow like any other
        # failure. The manual flow needs no optional package, so it really is
        # the right thing to do next -- but reporting this as "failed to fetch
        # a token using a web browser" told the user nothing about the 'login'
        # extra, and they would take the manual flow every time without ever
        # learning why. Both properties matter: say what is wrong, and still
        # get them a token.
        #
        # Not narrowed to the missing-extra message. import_optional re-raises
        # an ImportError from inside an installed package unchanged, and a
        # broken werkzeug under flask is no more a reason to refuse the manual
        # flow than a missing one.
        print(exc, file=sys.stderr)
        print('Falling back to the manual flow.', file=sys.stderr)
    except Exception:
        # Deliberately not a bare 'except:'. That caught KeyboardInterrupt and
        # SystemExit too, so a Ctrl-C at the login prompt fell through into the
        # manual flow rather than quitting.
        print('Failed to fetch a token using a web browser, falling back to '
                'the manual flow')

    schwab.auth.client_from_manual_flow(api_key, app_secret, callback_url,
                                        token_path)

    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            description='Fetch a new token and write it to a file')

    required = parser.add_argument_group('required arguments')
    required.add_argument(
            '--token_file', required=True,
            help='Path to token file. Any existing file will be overwritten')
    required.add_argument('--api_key', required=True)
    required.add_argument('--app_secret', required=True)
    required.add_argument('--callback_url', required=True, type=str)
    required.add_argument(
            '--browser', required=False, type=str,
            help='Manually specify a browser in which to start the login '+
            'flow. See here for available options: '+
            'https://docs.python.org/3/library/webbrowser.html#webbrowser.register')

    args = parser.parse_args()

    sys.exit(main(args.api_key, args.app_secret, args.callback_url,
                  args.token_file, args.browser))
