#!/bin/bash

# JSON file containing VPS information
JSON_FILE="vps.json"

# Function to read and display the banner from .banner.txt
display_banner() {
  if [ -f ".banner.txt" ]; then
    cat .banner.txt
  else
    echo "-----------------------------------"
    echo "            VPScope                "
    echo "-----------------------------------"
  fi
}

# Function to read the JSON file and execute commands
run_commands_on_vps() {
  local json_file=$1

  while true; do
    # Prompting for a command from the user
    read -p "Input your command: " command

    # Reading VPS information from the JSON file
    local vps_list=$(jq -c '.vps[]' "$json_file")

    # Loop through each VPS and execute the command
    for vps in $vps_list; do
      local hostname=$(echo "$vps" | jq -r '.hostname')
      local username=$(echo "$vps" | jq -r '.username')
      local password=$(echo "$vps" | jq -r '.password')

      echo -e "\nConnecting to $hostname..."
      # Executing the command on the VPS
      sshpass -p "$password" ssh -o StrictHostKeyChecking=no "$username@$hostname" "$command"
      if [ $? -ne 0 ]; then
        echo "Failed to execute command on $hostname"
      fi
    done

    read -p "The command has been applied successfully, wanna add more? (y/n): " choice
    if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
      break
    fi
  done
}

# Function to add VPS to the JSON file
add_vps() {
  local json_file=$1
  while true; do
    read -p "Enter VPS hostname: " hostname
    read -p "Enter VPS username: " username
    read -sp "Enter VPS password: " password
    echo

    # Adding new VPS information to the JSON file
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

# Function to remove VPS from the JSON file
remove_vps() {
  local json_file=$1
  while true; do
    # Displaying the list of current VPS
    echo -e "\nCurrent VPS List:"
    jq -r '.vps[] | "\(.hostname) \(.username)"' "$json_file" | nl

    # Prompting the user to select the VPS to delete
    read -p "Select the number of the VPS to delete (or 0 to cancel): " number

    if [ "$number" -eq 0 ]; then
      echo -e "\nDeletion canceled."
      break
    fi

    # Deleting the selected VPS
    jq --argjson number "$number" 'del(.vps[$number - 1])' "$json_file" > tmp.json && mv tmp.json "$json_file"

    echo -e "\nVPS number $number has been deleted from $json_file"

    read -p "Do you want to remove more VPS? (y/n): " choice
    if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
      break
    fi
  done
}

# Main menu
while true; do
  clear
  display_banner
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
