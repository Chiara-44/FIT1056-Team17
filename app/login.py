def validate_password(username, password, role):
    """Pasword validation Function"""

    if role == :
        #adding password function
        passcode=input("Enter access code: ")
        if passcode=="ilove1056@":
            current_role="admin"
            print("Admin access granted.")
        else:
            print("Incorrect code.")

    elif choice=="2":
        current_role="receptionist"
        print("Switched to receptionist.")

    else:
        print("Invalid choice.")

    print(f"Current User: {current_role}")