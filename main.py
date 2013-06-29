from flask import Flask, request, Response, make_response
import werkzeug.wsgi

from functools import wraps

import subprocess
import subprocessio
import os

import logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username and password

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def git_rpc_handler(repo_path, git_command):
    wsgi_input = request.environ.get('wsgi.input')
    content_length = int(request.headers['Content-Length'])
    stdin = werkzeug.wsgi.make_limited_stream(wsgi_input, content_length)

    try:
        out = subprocessio.SubprocessIOChunker(
            r'git %s --stateless-rpc "%s"' % (git_command[4:], repo_path),
            inputstream = stdin
        )
    except:
        raise Exception('RPC Failed')

    if git_command == u'git-receive-pack':
        # updating refs manually after each push. Needed for pre-1.7.0.4 git clients using regular HTTP mode.
        subprocess.call(u'git --git-dir "%s" update-server-info' % repo_path, shell=True)

    logging.debug(('out', out))
    headers = [('Content-type', 'application/x-%s-result' % git_command.encode('utf8'))]
    return make_response((out, "200 OK", headers))

def git_inforefs(repo_path, git_command):
    answer = basic_checks()
    if answer:
        return answer
    smart_server_advert = '# service=%s' % git_command

    try:
        logging.debug(('trying: ', r'git %s --stateless-rpc --advertise-refs "%s"' % (git_command[4:], repo_path)))
        out = subprocessio.SubprocessIOChunker(
            r'git %s --stateless-rpc --advertise-refs "%s"' % (git_command[4:], repo_path),
            starting_values = [ str(hex(len(smart_server_advert)+4)[2:].rjust(4,'0') + smart_server_advert + '0000') ]
        )
    except:
        raise Exception('Inforefs work')

    headers = [('Content-type','application/x-%s-advertisement' % str(git_command))]
    return make_response((out, "200 OK", headers))

@app.route('/<working_path>/info/refs')
@requires_auth
def do_git_inforefs_handler(working_path):
    logging.debug((request.authorization))
    working_path = os.path.join('/Users/jspies/Downloads/gitrepos/', working_path)
    git_command = request.args.get('service')
    return git_inforefs(working_path, git_command)

@app.route('/<working_path>/<git_command>', methods=['POST'])
def do_git_rpc_handler(working_path, git_command):
    working_path = os.path.join('/Users/jspies/Downloads/gitrepos/', working_path)
    return git_rpc_handler(working_path, git_command)

@app.route('/<working_path>')
def do_generic_handler(working_path):
    working_path = os.path.join('/Users/jspies/Downloads/gitrepos/', working_path)

if __name__ == "__main__":
    app.run(port=8080, debug=True)