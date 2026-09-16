from PIL import Image, ImageDraw
def make(text, name):
    img=Image.new('RGB',(800,400),'white')
    d=ImageDraw.Draw(img)
    d.text((20,20),text,fill='black')
    img.save(f'uploads/{name}')
    print(f'Created {name}')

make("APPLICATION FORM - CAPABL SCHEME\nName: RAJ KUMAR SHARMA\nDOB: 01/02/2000\nAddress: 12, MG Road, Bangalore - 560001\nApplication ID: CAP2024-12345","doc1_application.png")
make("STATE BOARD MARKSHEET\nName: Rajkumar Sharma\nDate of Birth: 1 Feb 2000\nAddress: 12 M.G. Road, Bangalore 560001\nRoll No: CAP2024-12345","doc2_marksheet.png")
make("ID CARD\nName: RAJ KUMAR SHARMA\nDOB: 15/08/1999\nAdd: 12, MG Road, Bangalore - 560001\nID No: CAP2024-12345","doc3_idcard.png")