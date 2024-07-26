# VPScope
A simple Bash script to manage Virtual Private Servers (VPS) by running commands, adding, and removing VPS details stored in a JSON file.

## Features

- Execute commands on multiple VPS instances.
- Add new VPS details to the JSON file.
- Remove VPS details from the JSON file.

## Prerequisites

- `sshpass`: A non-interactive ssh password authentication tool.
- `jq`: A lightweight and flexible command-line JSON processor.

## Installation

1. Install `sshpass` and `jq` if they are not already installed:

   ```bash
   sudo apt-get install sshpass jq -y

2. Clone the repository:

   ```bash
   git clone https://github.com/suuf24/vpscope
   cd vpscope
   touch vps.json
   chmod +x vpscope.sh

## Usage

1. Run the script

   ```bash
   ./vpscope.sh

2. Follow the on-screen menu to choose your desired action:

   Run Commands: Execute commands on all VPS instances listed in the JSON file.
   Add VPS: Add new VPS details to the JSON file.
   Remove VPS: Remove existing VPS details from the JSON file.
   Exit: Exit the script.

## Script Detail

JSON File
The script uses a JSON file (vps.json) to store VPS information. The structure of the JSON file is as follows:
```bash
{
  "vps": [
    {
      "hostname": "yourvpsip",
      "username": "root",
      "password": "password"
    }
  ]
}
```

## Functions
`run_commands_on_vps`
This function reads the JSON file and executes a command on each VPS.

`add_vps`
This function prompts the user to enter new VPS details and adds them to the JSON file.

`remove_vps`
This function displays the list of VPS entries and allows the user to delete a selected VPS.

`Main Menu`
The main menu provides options to run commands, add VPS, remove VPS, or exit the script.

## License
This project is licensed under the MIT License.

## Author
@suuf24

Feel free to reach out if you have any questions or suggestions.

This README provides an overview of the script, its features, installation instructions, usage, and a brief description of its functionality. You can customize it further based on your specific needs or preferences.
