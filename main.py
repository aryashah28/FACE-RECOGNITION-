def main():
    print("* Face Recognition Login System *")
    print("1. Register")
    print("2. Login")

    choice = input("Enter choice: ")

    if choice == "1":
        from register import register_user
        register_user()
    elif choice == "2":
        from login import login_user
        login_user()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()