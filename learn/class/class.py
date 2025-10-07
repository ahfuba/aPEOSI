import csv

class User:
    def __init__(USER_INIT, username, pwd):
        USER_INIT.username = username
        USER_INIT.pwd = pwd
        print("Welcome to the system")
        USER_INIT.action = input("Type \"l\" to login or \"r\" to register:")
        if USER_INIT.action == "r":
            USER_INIT.regis(USER_INIT)
        elif USER_INIT.action == "l":
            USER_INIT.login(USER_INIT)
        else:
            print("Invalid input, please try again.")
            USER_INIT.action = input("Type \"l\" to login or \"r\" to register:")
            return USER_INIT.__init__(USER_INIT, "", "")

    def regis(USER_REGIS):
        USER_REGIS.regis_username = input("USERNAME:")
        USER_REGIS.regis_pwd = input("Password:")
        USER_REGIS.regis_pwd_again = input("Password again:")

        if USER_REGIS.regis_pwd == USER_REGIS.regis_pwd_again:
            with open("user.csv", "a", newline='') as file:
                writer = csv.writer(file)
                writer.writerow([USER_REGIS.regis_username, USER_REGIS.regis_pwd])
            print("Registration successful")
        else:
            print("Passwords do not match, please try again.")
            USER_REGIS.regis_pwd_again = input("Password again:")



    def login(USER_LOGIN):
        USER_LOGIN.login_username = input("USERNAME:")
        USER_LOGIN.login_pwd = input("Password:")

        with open("user.csv", "r") as file:
            reader = csv.reader(file)
            for row in reader:
                if USER_LOGIN.login_username == row[0] and USER_LOGIN.login_pwd == row[1]:
                    print("Login successful")
                    return
            print("Incorrect username or password, please try again.")
            USER_LOGIN.login_username = input("USERNAME:")
            USER_LOGIN.login_pwd = input("Password:")
            return USER_LOGIN.login(USER_LOGIN)

User.__init__(User, "", "")
