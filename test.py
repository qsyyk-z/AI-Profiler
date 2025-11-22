import requests
import os

def upload_to_transfersh(file_path):
        with open(file_path, 'rb') as f:
            response = requests.put('https://transfer.sh/' + os.path.basename(file_path), data=f)
        if response.status_code == 200:
            return response.text.strip()
        else:
            raise Exception(f"Upload failed: {response.status_code}")
        
url = upload_to_transfersh("knowledges/lecture02.pdf")
print(url)