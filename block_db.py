import modal


app = modal.App(name="bitcoin-explore-fy")

db_volume = modal.Volume.from_name("fy_mysql_db")

db_image = modal.Image.from_dockerfile("./mysql-db")


# Define the MySQL service
@app.function(
    image=db_image,
    keep_warm=1,
    # secrets=[
    #     modal.Secret.from_dotenv()  # Looks for `.env` in the current working directory
    # ],
    volumes={"/var/lib/mysql": db_volume},  # Mount volume to MySQL data directory
    # secret=modal.Secret.from_dict({"MYSQL_ROOT_PASSWORD": "my-secret-pw"}),  # Securely store credentials
)
def run_mysql():
    import subprocess
    
    # Start MySQL in the foreground so the function blocks here.
    # 'mysqld' is the server daemon in the official MySQL image.
    proc = subprocess.Popen(["mysqld"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Optionally, read or print logs
    for line in proc.stderr:
        print(line.decode(), end="")

    # Wait for MySQL to exit (which will also end the function)
    proc.wait()
    print("MySQL exited with code:", proc.returncode)