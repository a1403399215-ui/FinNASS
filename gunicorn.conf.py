"""Production server settings; Cloud Run provides PORT."""
import os

bind = '0.0.0.0:' + os.environ.get('PORT', '8080')
workers = 1
threads = 4
timeout = 60
accesslog = '-'
errorlog = '-'
capture_output = True
preload_app = False
