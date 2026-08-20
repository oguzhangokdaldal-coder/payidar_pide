from flask import Flask, render_template

app = Flask(__name__)

PRODUCTS = [
    {"id": 1, "category": "pide", "name": "Payidar Karışık", "description": "Kuşbaşı, kaşar, sucuk ve közlenmiş biber", "price": 290, "tag": "Favori", "image": "https://images.unsplash.com/photo-1594007654729-407eedc4be65?auto=format&fit=crop&w=700&q=85"},
    {"id": 2, "category": "pide", "name": "Kuşbaşılı Pide", "description": "Zırh kıyması, domates, biber ve kaşar", "price": 250, "tag": "Yeni", "image": "https://images.unsplash.com/photo-1579751626657-72bc17010498?auto=format&fit=crop&w=700&q=85"},
    {"id": 3, "category": "kebap", "name": "Adana Kebap", "description": "Zırhta çekilmiş et, köz sebzeler ve lavaş", "price": 310, "tag": "", "image": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=700&q=85"},
    {"id": 4, "category": "yan", "name": "Fırın Sütlaç", "description": "Geleneksel tarif, çıtır fındık dokunuşuyla", "price": 95, "tag": "Tatlı", "image": "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?auto=format&fit=crop&w=700&q=85"},
    {"id": 5, "category": "pide", "name": "Kaşarlı Pide", "description": "Uzayan kaşar, tereyağı ve çıtır hamur", "price": 210, "tag": "", "image": "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=700&q=85"},
    {"id": 6, "category": "yan", "name": "Közlenmiş Biber", "description": "Taş fırında közlenmiş, zeytinyağlı", "price": 80, "tag": "", "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=700&q=85"},
    {"id": 7, "category": "kebap", "name": "Kuzu Şiş", "description": "Lokum kıvamında kuzu, pilav ve köz", "price": 360, "tag": "", "image": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=700&q=85"},
    {"id": 8, "category": "yan", "name": "Yayık Ayran", "description": "Günlük yoğurttan, buz gibi", "price": 45, "tag": "", "image": "https://images.unsplash.com/photo-1628088062854-d1870b4553da?auto=format&fit=crop&w=700&q=85"},
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
#bu işaret yorum işaretidir. kod burayı okumaz......