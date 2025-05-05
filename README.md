# Project Name

**Author:** Your Name Here  
**Email:** your.email@example.com

## Overview

This project provides a command-line module and robot management system using Python and SQLAlchemy. It enables:

- Dynamic creation and selection of robots with unique UUIDs and password protection.  
- Status tracking for both modules and robots using three states: **IDLE**, **RUNNING**, and **FAILED**.  
- Secure communication over TCP sockets by sending JSON-encoded status updates between modules and their parent robot.  
- Persistent storage of robots and modules metadata in a SQLite database (default) with timezone-aware timestamps.  

## Key Concepts

### UUIDs

- Every **Robot** and **Module** is identified by a universally unique identifier (UUID) generated automatically.  
- The `id` field in both tables uses `uuid.uuid4()` by default.  

### Status States

- **IDLE**: The module/robot is inactive and awaiting commands.  
- **RUNNING**: The module/robot is actively processing or executing tasks.  
- **FAILED**: The module/robot encountered an error or could not complete its last operation.  

Status transitions are enforced in the CLI:

1. Prompt user to enter new status (`RUNNING`, `IDLE`, `FAILED`).  
2. Invalid entries are rejected with a reminder of valid options.  
3. On valid status change, the new state and UTC timestamp (`last_online`) are recorded.  

### Ports

- Each **Robot** listens on a configurable TCP port for incoming module connections.  
- Each **Module** sends updates to its parent robot using the robot’s IP address and port.  
- Default port values can be overridden via the command-line prompts or in the database.  

### Password and Logging

- During robot creation, a password is set via a secure prompt (`getpass`).  
- Subsequent connections require the correct password before the CLI will proceed.  
- All password inputs are *never* echoed to the terminal.  

## Installation

1. Clone the repository:  
   ```bash
   git clone https://github.com/yourusername/your-repo.git
   cd your-repo
   ```
2. Create a Python virtual environment and activate it:  
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:  
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Robot CLI

1. **Create or select** a robot:  
   ```bash
   python robot.py
   ```  
   - If no robots exist, you will be prompted for name, owner, email, SSID, password, IP, port, and password.  
   - If robots exist, select by UUID and enter the password.  
2. **Start the server**:  
   ```bash
   python robot.py
   ```  
   - The robot will listen on the configured IP and port.  
   - Incoming module status updates will be processed and reflected in the database.  

### Module CLI

1. **Invoke module** with its UUID:  
   ```bash
   python module.py <MODULE_UUID>
   ```  
2. **Enter status** when prompted:  
   ```text
   Enter new status (RUNNING, IDLE, FAILED):
   ```  
3. **Output**:  
   - On change, prints `Updated → status=<STATE>, last_online=<TIMESTAMP>`.  
   - Sends JSON `{ "module_id": "<UUID>", "status": "<STATE>" }` to the parent robot.  
   - On `KeyboardInterrupt`, exits gracefully.  

## Database Schema

- **robots** table:  
  - `id` (UUID primary key)  
  - `name`, `owner`, `owner_email`, `status`, `last_online`, `network_ssid`, `network_password`, `ip_address`, `port`, `password`  

- **modules** table:  
  - `id` (UUID primary key)  
  - `name`, `type`, `ip_address`, `port`, `last_online`, `status`, `robot_id` (foreign key)  

## Testing

Run the pytest suite:  
```bash
pytest --maxfail=1 --disable-warnings -q tests/
```  

## Contributors

- Your Name Here (josh.bardwick@gmail.com)  