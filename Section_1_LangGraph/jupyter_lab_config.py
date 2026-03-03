# Jupter Lab Server Configuration File
# jupyter lab --config jupyter_lab_config.py

# Set ip to '*' to bind on all interfaces (ips) for the public server
c.NotebookApp.ip = '*'

# There's no browser in container (no x11)
c.NotebookApp.open_browser = False

# Access on port 8888
c.NotebookApp.port = 8888

# Allow root, required by runtime in container
c.NotebookApp.allow_root = True