from app.database import mongodb


def main():
    mongodb.connect()

    print("Database:", mongodb.database.name)
    print("Collection:", mongodb.collection.name)

    mongodb.close()


if __name__ == "__main__":
    main()