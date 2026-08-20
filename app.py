from flask import Flask, render_template

app = Flask(__name__)

PRODUCTS = [
    {"id": 1, "category": "pide", "name": "Payidar Karışık", "description": "Kuşbaşı, kaşar, sucuk ve közlenmiş biber", "price": 290, "tag": "Favori", "image": "img/karısik_pizza.jpg"},
    {"id": 2, "category": "pide", "name": "Kuşbaşı Kaşarlı Pide", "description": "Zırh kıyması, bol kaşar ve tereyağı", "price": 260, "tag": "Yeni", "image": "img/kusbasi_kasar.jpg"},
    {"id": 3, "category": "pide", "name": "Kıymalı Pide", "description": "İnce kıyma, domates, biber ve maydanoz", "price": 230, "tag": "", "image": "img/kiymali.jpg"},
    {"id": 4, "category": "pide", "name": "Kaşarlı Pide", "description": "Uzayan kaşar, tereyağı ve çıtır hamur", "price": 210, "tag": "", "image": "img/kasarlipide.jpg"},
    {"id": 5, "category": "pide", "name": "Sucuklu Kaşarlı Pide", "description": "Baharatlı sucuk ve bol kaşar", "price": 250, "tag": "", "image": "img/sucuklu_kasar.jpg"},
    {"id": 6, "category": "pide", "name": "Lahmacun", "description": "İnce açılmış hamur, bol malzeme, taş fırında", "price": 90, "tag": "", "image": "img/lahmacun.jpg"},
    {"id": 7, "category": "kebap", "name": "Adana veya Urfa Kebap", "description": "Zırhta çekilmiş et, köz sebzeler ve lavaş", "price": 310, "tag": "", "image": "img/adana_veya_urfa.jpg"},
    {"id": 8, "category": "yan", "name": "Fırın Sütlaç", "description": "Geleneksel tarif, çıtır fındık dokunuşuyla", "price": 95, "tag": "Tatlı", "image": ""},
    {"id": 9, "category": "yan", "name": "Közlenmiş Biber", "description": "Taş fırında közlenmiş, zeytinyağlı", "price": 80, "tag": "", "image": ""},
    {"id": 10, "category": "yan", "name": "Yayık Ayran", "description": "Günlük yoğurttan, buz gibi", "price": 45, "tag": "", "image": ""},
]

CAMPAIGNS = [
    {"label": "HAFTANIN PAYLAŞIMI", "title": "2 Pide + 1 Ayran = 490₺", "description": "Payidar Karışık veya Kuşbaşılı Pide'den ikisini seç, yanına ayranı ekleyelim."},
    {"label": "ÖĞLE FIRSATI", "title": "Hafta içi 12:00-15:00 arası %15 indirim", "description": "Tüm pide ve kebaplarda geçerli, ekstra bir işlem gerekmiyor."},
    {"label": "AİLE SOFRASI", "title": "4 Kişilik Karma Menü 990₺", "description": "2 pide, 1 kebap, 2 yan ürün ve 4 ayran bir arada."},
]


@app.route("/")
def home():
    return render_template("index.html", active="home")


@app.route("/menu")
def menu():
    return render_template("menu.html", products=PRODUCTS, active="menu")


@app.route("/kampanyalar")
def campaigns():
    return render_template("campaigns.html", campaigns=CAMPAIGNS, active="campaigns")


@app.route("/biz-kimiz")
def about():
    return render_template("about.html", active="about")


@app.route("/iletisim")
def contact():
    return render_template("contact.html", active="contact")


if __name__ == "__main__":
    app.run(debug=True)
