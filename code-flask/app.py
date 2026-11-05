from flask import Flask, redirect, render_template_string, request

from base import ouvrir_base

# Le HTML de la page.
PAGE = """

<h1>Partage de frais</h1>

<h2>Membres</h2>
<ul>
  {% for membre in membres %}
    <li>{{ membre["nom"] }}</li>
  {% endfor %}
</ul>

<form method="post" action="/membres">
  <input name="nom" placeholder="Nom" required>
  <button>Ajouter</button>
</form>

<div style="text-align: center;">
  <img src="TP1_expertise/logo_tricount.jpg" alt="Tricount" width="200" height="200">
</div>

"""

app = Flask(__name__)


# Page d'accueil : lit les membres et affiche PAGE.
@app.get("/")
def accueil():
    with ouvrir_base() as conn:
        membres = conn.execute("SELECT nom FROM membres").fetchall()
        groupes = conn.execute("SELECT nom FROM groupes").fetchall()
    return render_template_string(PAGE, membres=membres)


@app.post("/membres")
def ajouter_membre():
    nom = request.form["nom"]
    groupe_id = request.form["groupe_id"]

    with ouvrir_base() as conn:
        conn.execute(
            "INSERT INTO membres (groupe_id, nom) VALUES (?, ?)",
            [groupe_id, nom]
        )

    return redirect("/")


@app.post("/groupes")
def ajouter_groupe():
    nom = request.form["nom"]
    date_debut = request.form["date_debut"]
    date_fin = request.form["date_fin"]

    with ouvrir_base() as conn:
        conn.execute(
            "INSERT INTO groupes (nom, date_debut, date_fin) VALUES (?, ?, ?)",
            [nom, date_debut, date_fin]
        )

    return redirect("/")

@app.post("/depenses")
def ajouter_depenses():
    groupe_id = request.form["groupe_id"]
    libelle = request.form["libelle"]
    montant_centimes = request.form["montant_centimes"]
    date = request.form["date"]
    payeur_id = request.form["payeur_id"]

    with ouvrir_base() as conn:
        conn.execute(
            "INSERT INTO depenses (groupe_id, libelle, montant_centimes, date, payeur_id) )",
            [groupe_id, libelle, montant_centimes, date, payeur_id]
        )

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
