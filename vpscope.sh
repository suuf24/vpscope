#!/bin/bash

# JSON file containing VPS information
JSON_FILE="vps.json"

# Load banner from .banner.txt
BANNER_FILE=".banner.txt"

# Function to read JSON file and execute commands
run_commands_on_vps() {
  local json_file=$1

  while true; do
    # Prompt user for command
    read -p "Input your command (or press CTRL+D to cancel): " command
    if [ $? -ne 0 ]; then
      echo -e "\nCommand input canceled."
      break
    fi

    # Read VPS information from JSON file
    local vps_list=$(jq -c '.vps[]' "$json_file")

    # Loop through each VPS and execute command
    for vps in $vps_list; do
      local hostname=$(echo "$vps" | jq -r '.hostname')
      local username=$(echo "$vps" | jq -r '.username')
      local password=$(echo "$vps" | jq -r '.password')

      echo -e "\nConnecting to $hostname..."
      # Execute command on VPS
      sshpass -p "$password" ssh -o StrictHostKeyChecking=no "$username@$hostname" "$command"
      if [ $? -ne 0 ]; then
        echo "Failed to execute command on $hostname"
      fi
    done

    read -p "The command has been applied successfully, do you want to add more? (y/n): " choice
    if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
      break
    fi
  done
}

# Function to add VPS to JSON file
add_vps() {
  local json_file=$1
  while true; do
    read -p "Enter VPS hostname: " hostname
    read -p "Enter VPS username: " username
    read -sp "Enter VPS password: " password
    echo

    # Add new VPS information to JSON file
    jq --arg hostname "$hostname" --arg username "$username" --arg password "$password" \
      '.vps += [{"hostname": $hostname, "username": $username, "password": $password}]' \
      "$json_file" > tmp.json && mv tmp.json "$json_file"

    echo -e "\nVPS has been added to $json_file"

    read -p "Do you want to add more VPS? (y/n): " choice
    if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
      break
    fi
  done
}

# Function to remove VPS from JSON file
remove_vps() {
  local json_file=$1
  while true; do
    # Display the list of existing VPS
    echo -e "\nCurrent VPS List:"
    jq -r '.vps[] | "\(.hostname) \(.username)"' "$json_file" | nl

    # Prompt user to select VPS to delete
    read -p "Select the number of the VPS to delete (or 0 to cancel): " number

    if [ "$number" -eq 0 ]; then
      echo -e "\nDeletion canceled."
      break
    fi

    # Remove selected VPS
    jq --argjson number "$number" 'del(.vps[$number - 1])' "$json_file" > tmp.json && mv tmp.json "$json_file"

    echo -e "\nVPS number $number has been deleted from $json_file"

    read -p "Do you want to remove more VPS? (y/n): " choice
    if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
      break
    fi
  done
}

# Load and display banner
display_banner() {
  if [ -f "$BANNER_FILE" ]; then
    cat "$BANNER_FILE"
  fi
}

# Main menu
while true; do
  clear
  display_banner
  echo "-----------------------------------"
  echo "            VPScope Manager            "
  echo "-----------------------------------"
  echo "1. Run Commands"
  echo "2. Add VPS"
  echo "3. Remove VPS"
  echo "0. Exit"
  echo "-----------------------------------"
  read -p "Select an option [0-3]: " option

  case $option in
    1)
      run_commands_on_vps "$JSON_FILE"
      ;;
    2)
      add_vps "$JSON_FILE"
      ;;
    3)
      remove_vps "$JSON_FILE"
      ;;
    0)
      exit 0
      ;;
    *)
      echo -e "\nInvalid option. Please choose again."
      ;;
  esac
done
