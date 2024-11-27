# Overview
**BKPMGT** is a centralized backup and recovery backend designed for scalability and **multi-client** support. The key components of its technology stack include:

- **Uvicorn**: An ASGI server enabling efficient handling of multiple concurrent connections, supporting real-time functionality.

- **FastAPI**: Powers the microservices architecture, offering robust and asynchronous handling of API requests.

- **GraphQL**: Facilitates flexible and efficient querying of data by clients, allowing them to specify the exact data they need while optimizing performance and reducing payload size.

- **RabbitMQ**: Manages task allocation and ensures smooth handling of asynchronous messaging for multi-client environments.

- **MongoDB**: Provides a NoSQL database for persisting functional data, ensuring high availability and scalability.

- **Websockets**: Manages bidirectional communication for real-time updates, control commands, and connection reliability.
# System Requirements
## Server
### OS, applications, packages & cmdlets:
- Either **Windows** or **Linux** with **Docker** installed and **running**.
- `docker-compose` is required for `run_server.*` automation scripts.
### Ports:
|PORT|Container / App|
|-|-|
|5672, 15672|RabbitMQ|
|27017|MongoDB|
|5000|GQL Endpoint|
## Client
### OS, applications, packages & cmdlets:
- Linux needs `dmidecode` to be installed for `system_uuid` resolution
```bash
sudo pacman -S dmidecode # for Arch based systems
```
- Only the `systemd` init system is supported for linux
### Ports:
|PORT|Container / App|
|-|-|
|8080|Web UI|
# Usage
## Install Dependencies
- This project supports the following dependency management systems
    - requirements.txt (un-versioned)
    - poetry
    - magic

- Navigate to **project root** (`bkpmgt/`) before setting up dependencies.

- Using requirements.txt (*for development only!*)
```bash
py -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt
```
- Windows (poetry)
```powershell
py -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install poetry && poetry install
```
- Linux (poetry)
```bash
py -m venv .venv && source .venv/bin/activate && pip install poetry && poetry install
```
- Linux only! (magic)
```bash
# If you don't have magic installed
curl -ssL https://magic.modular.com/8301f3c2-24f7-4144-8bcf-4ba9c94d4588 | bash # as magic isn't a pypi package

magic install
```

- For manual usage, the `mongo` & `rabbitmq` containers need to be up
- The ASGI server should be started with the following command after navigating to `srvr/` from project root & activating the `venv`.
```bash
uvicorn srvr:app --host 0.0.0.0 --port 5000
```
## Automation
- Without activating the `venv` you can run the following scripts from project root (based on your OS) to start the BKPMGT server & containers it depends on
- Make sure **Docker** is **running**!
```powershell
.\run_server.ps1 # Windows
```

```bash
.\run_server.sh # Linux
```
# Compiling Installer Binaries
- Binaries can be created for this project using the `pyinstaller` package if you'd like to manually comple specific binaries

The following packages need to be present in the specified directories for compiling the installer:
- restic (ELF or EXE) in `bkpmgt/clnt/`
- wazuh (DEB or MSI) in `bkpmgt/installer/`
- nssm (EXE, windows exclusive!) in `bkpmgt/installer/`

### Windows
```powershell
# create build
.\installer\build_scripts\windows_build.ps1
# cleanup old build
.\installer\build_scripts\windows_cleanup.ps1
```
### Linux
```bash
# create build
./installer/build_scripts/linux_build.sh
# cleanup old build
./installer/build_scripts/linux_cleanup.sh
```

## Packaging flow
Restic binary bundled with client → Client binary compiled → Wazuh binary bundled with `package` → nssm binary bundled with `package` (Windows only!) → Installer binary compiled to result in final `package`

---