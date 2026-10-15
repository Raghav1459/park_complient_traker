# ParkCare — VTU Project 71

A beginner-friendly public park and garden maintenance complaint tracker built with Flask and SQLite.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer (the Python installer should add the `py` launcher)
- Internet access the first time, so pip can install Flask packages

## Run ParkCare

1. Open the project folder in File Explorer.
2. Double-click `run_parkcare.bat`. The first run creates a `.venv` virtual environment and installs the dependencies.
3. Keep the command window open while using the website.
4. Visit **http://127.0.0.1:5000** in your browser. This address is available only on the computer running ParkCare; the website is not publicly hosted.
5. To stop the server, press **Ctrl+C** in the command window.

## Create an administrator account

Open Command Prompt in the project folder and run:

```bat
.venv\Scripts\python.exe -m flask --app app create-admin
```

Enter a username and a password of at least 12 characters when prompted. The password is stored as a secure hash. To change it, run the command again with the same username. Admin credentials are entered locally and are never placed in the source files.

## Local data

ParkCare creates `instance/secret_key`, the persistent SQLite database at `instance/parkcare.sqlite3`, and an `instance/uploads/` folder for images. These are local application data and are excluded from Git. Back up the `instance` folder to preserve reports and photos.

## Included features

- Citizen complaint submission with validation and optional JPG, PNG, or WebP photo (up to 5 MB)
- Randomized photo filenames and unique tracking IDs
- Public lookup of a report's status and update history using its tracking ID
- Admin login, status filters, queue counts, and status updates with optional notes
- CSRF protection, parameterized SQLite queries, hashed admin passwords, and protected admin photo access

All records are stored on this computer. Configure a production server and HTTPS before exposing a deployment to a network.
