from app.services.file_hash import calculate_file_hash


PDF_PATH = "data/technical_manual.pdf"


def main():
    file_hash = calculate_file_hash(PDF_PATH)

    print("SHA-256:")
    print(file_hash)
    print("Hash length:", len(file_hash))


if __name__ == "__main__":
    main()