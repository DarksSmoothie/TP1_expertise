from flask import Flask, redirect, render_template_string, request
from base import ouvrir_base

app = Flask(__name__)

PAGE = """
<body style="background-image: url('{{ url_for('static', filename='photo.png') }}'); background-size: 1400px; background-repeat: no-repeat;">

<h1>Partage de frais</h1>

<div style="text-align: center;">
    <img src="{{ url_for('static', filename='transparent.png') }}" width="600" height="400">
</div>

<h2>Groupes</h2>
<ul>
{% for g in groupes %}
    <li>{{ g["id"] }} - {{ g["nom"] }}</li>
{% endfor %}
</ul>

<form method="post" action="/groupes">
    <input name="nom" placeholder="Nom du groupe" required>
    <input name="date_debut" type="date" required>
    <input name="date_fin" type="date" required>
    <button>Ajouter</button>
</form>


<h2>Membres</h2>
<ul>
{% for m in membres %}
    <li>{{ m["id"] }} - {{ m["nom"] }} (Groupe {{ m["groupe_id"] }})</li>
{% endfor %}
</ul>

<form method="post" action="/membres">
    <input name="nom" placeholder="Nom" required>
    <input name="groupe_id" type="number" placeholder="ID du groupe" required>
    <button>Ajouter</button>
</form>


<h2>Catégories</h2>
<ul>
{% for c in categories %}
    <li>{{ c["id"] }} - {{ c["nom"] }}</li>
{% endfor %}
</ul>

<form method="post" action="/categories">
    <input name="nom" placeholder="Nom de la catégorie" required>
    <button>Ajouter</button>
</form>


<h2>Dépenses</h2>
<ul>
{% for d in depenses %}
    <li>
        {{ d["id"] }} - {{ d["libelle"] }} :
        {{ "%.2f"|format(d["montant_centimes"] / 100) }} €
    </li>
{% endfor %}
</ul>

<form method="post" action="/depenses">
    <input name="groupe_id" type="number" placeholder="ID du groupe" required>
    <input name="libelle" placeholder="Libellé" required>

    <select name="categorie_id" required>
        {% for c in categories %}
            <option value="{{ c['id'] }}">{{ c["nom"] }}</option>
        {% endfor %}
    </select>

    <input name="montant_centimes" type="number" min="1" placeholder="Montant (centimes)" required>
    <input name="date" type="date" required>
    <input name="payeur_id" type="number" placeholder="ID du payeur" required>
    <input name="participants" placeholder="Participants : 1,2,3" required>
    <button>Ajouter</button>
</form>


<h2>Supprimer une dépense</h2>
<form method="post" action="/depenses/supprimer">
    <input name="id" type="number" placeholder="ID de la dépense" required>
    <button>Supprimer</button>
</form>


<h2>Remboursements</h2>
<ul>
{% for r in remboursements %}
    <li>
        {{ r["payeur_id"] }} rembourse
        {{ r["beneficiaire_id"] }} :
        {{ "%.2f"|format(r["montant_centimes"] / 100) }} €
    </li>
{% endfor %}
</ul>

<form method="post" action="/remboursements">
    <input name="groupe_id" type="number" placeholder="ID du groupe" required>
    <input name="payeur_id" type="number" placeholder="ID de celui qui rembourse" required>
    <input name="beneficiaire_id" type="number" placeholder="ID de celui qui reçoit" required>
    <input name="montant_centimes" type="number" min="1" placeholder="Montant (centimes)" required>
    <input name="date" type="date" required>
    <button>Rembourser</button>
</form>


<h2>Soldes</h2>
<ul>
{% for m in membres %}
    <li>
        {{ m["nom"] }} (Groupe {{ m["groupe_id"] }}) :
        {{ "%.2f"|format(soldes[m["id"]] / 100) }} €
    </li>
{% endfor %}
</ul>

</body>
"""


@app.get("/")
def accueil():
    with ouvrir_base() as conn:
        groupes = conn.execute("SELECT * FROM groupes").fetchall()
        membres = conn.execute("SELECT * FROM membres").fetchall()
        categories = conn.execute("SELECT * FROM categories").fetchall()
        depenses = conn.execute("SELECT * FROM depenses").fetchall()
        remboursements = conn.execute("SELECT * FROM remboursements").fetchall()

    soldes = {}

    for g in groupes:
        soldes.update(calculer_soldes(g["id"]))

    return render_template_string(
        PAGE,
        groupes=groupes,
        membres=membres,
        categories=categories,
        depenses=depenses,
        remboursements=remboursements,
        soldes=soldes
    )


@app.post("/groupes")
def ajouter_groupe():
    nom = request.form["nom"].strip()
    debut = request.form["date_debut"]
    fin = request.form["date_fin"]

    if not nom or debut > fin:
        return "Nom ou dates invalides", 400

    with ouvrir_base() as conn:
        conn.execute(
            "INSERT INTO groupes (nom, date_debut, date_fin) VALUES (?, ?, ?)",
            [nom, debut, fin]
        )

    return redirect("/")


@app.post("/membres")
def ajouter_membre():
    nom = request.form["nom"].strip()
    groupe_id = request.form["groupe_id"]

    if not nom:
        return "Nom obligatoire", 400

    with ouvrir_base() as conn:
        groupe = conn.execute(
            "SELECT id FROM groupes WHERE id = ?", [groupe_id]
        ).fetchone()

        if groupe is None:
            return "Groupe inexistant", 400

        membre = conn.execute(
            "SELECT id FROM membres WHERE groupe_id = ? AND nom = ?",
            [groupe_id, nom]
        ).fetchone()

        if membre is not None:
            return "Ce nom existe déjà dans ce groupe", 400

        conn.execute(
            "INSERT INTO membres (groupe_id, nom) VALUES (?, ?)",
            [groupe_id, nom]
        )

    return redirect("/")


@app.post("/categories")
def ajouter_categorie():
    nom = request.form["nom"].strip()

    if not nom:
        return "Nom obligatoire", 400

    with ouvrir_base() as conn:
        conn.execute(
            "INSERT INTO categories (nom) VALUES (?)",
            [nom]
        )

    return redirect("/")


@app.post("/depenses")
def ajouter_depense():
    groupe_id = request.form["groupe_id"]
    libelle = request.form["libelle"].strip()
    categorie_id = request.form["categorie_id"]
    montant = int(request.form["montant_centimes"])
    date = request.form["date"]
    payeur_id = request.form["payeur_id"]
    participants = [p.strip() for p in request.form["participants"].split(",")]

    if montant <= 0 or not libelle:
        return "Dépense invalide", 400

    if not participants or "" in participants:
        return "Il faut au moins un participant", 400

    if len(participants) != len(set(participants)):
        return "Participants en double", 400

    with ouvrir_base() as conn:
        groupe = conn.execute(
            "SELECT * FROM groupes WHERE id = ?", [groupe_id]
        ).fetchone()

        if groupe is None:
            return "Groupe inexistant", 400

        if not (groupe["date_debut"] <= date <= groupe["date_fin"]):
            return "Date hors du séjour", 400

        categorie = conn.execute(
            "SELECT id FROM categories WHERE id = ?", [categorie_id]
        ).fetchone()

        if categorie is None:
            return "Catégorie inexistante", 400

        membres = conn.execute(
            "SELECT id FROM membres WHERE groupe_id = ?", [groupe_id]
        ).fetchall()

        ids = [str(m["id"]) for m in membres]

        if payeur_id not in ids:
            return "Payeur invalide", 400

        for p in participants:
            if p not in ids:
                return "Participant invalide", 400

        depense_id = conn.execute(
            """INSERT INTO depenses
            (groupe_id, libelle, categorie_id, montant_centimes, date, payeur_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            [groupe_id, libelle, categorie_id, montant, date, payeur_id]
        ).lastrowid

        for p in participants:
            conn.execute(
                "INSERT INTO participants (depense_id, membre_id) VALUES (?, ?)",
                [depense_id, p]
            )

    return redirect("/")


@app.post("/depenses/supprimer")
def supprimer_depense():
    depense_id = request.form["id"]

    with ouvrir_base() as conn:
        conn.execute(
            "DELETE FROM participants WHERE depense_id = ?",
            [depense_id]
        )
        conn.execute(
            "DELETE FROM depenses WHERE id = ?",
            [depense_id]
        )

    return redirect("/")


@app.post("/remboursements")
def ajouter_remboursement():
    groupe_id = request.form["groupe_id"]
    payeur_id = request.form["payeur_id"]
    beneficiaire_id = request.form["beneficiaire_id"]
    montant = int(request.form["montant_centimes"])
    date = request.form["date"]

    if montant <= 0:
        return "Montant invalide", 400

    if payeur_id == beneficiaire_id:
        return "Un membre ne peut pas se rembourser lui-même", 400

    with ouvrir_base() as conn:
        groupe = conn.execute(
            "SELECT * FROM groupes WHERE id = ?", [groupe_id]
        ).fetchone()

        if groupe is None:
            return "Groupe inexistant", 400

        if not (groupe["date_debut"] <= date <= groupe["date_fin"]):
            return "Date hors du séjour", 400

        membres = conn.execute(
            "SELECT id FROM membres WHERE groupe_id = ?", [groupe_id]
        ).fetchall()

        ids = [str(m["id"]) for m in membres]

        if payeur_id not in ids or beneficiaire_id not in ids:
            return "Membre invalide", 400

        conn.execute(
            """INSERT INTO remboursements
            (groupe_id, payeur_id, beneficiaire_id, montant_centimes, date)
            VALUES (?, ?, ?, ?, ?)""",
            [groupe_id, payeur_id, beneficiaire_id, montant, date]
        )

    return redirect("/")


def calculer_soldes(groupe_id):
    with ouvrir_base() as conn:
        membres = conn.execute(
            "SELECT id FROM membres WHERE groupe_id = ?", [groupe_id]
        ).fetchall()

        depenses = conn.execute(
            "SELECT * FROM depenses WHERE groupe_id = ?", [groupe_id]
        ).fetchall()

        remboursements = conn.execute(
            "SELECT * FROM remboursements WHERE groupe_id = ?", [groupe_id]
        ).fetchall()

        soldes = {m["id"]: 0 for m in membres}

        for d in depenses:
            participants = conn.execute(
                "SELECT membre_id FROM participants WHERE depense_id = ? ORDER BY rowid",
                [d["id"]]
            ).fetchall()

            montant = d["montant_centimes"]
            part = montant // len(participants)
            reste = montant % len(participants)

            soldes[d["payeur_id"]] += montant

            for p in participants:
                soldes[p["membre_id"]] -= part

            soldes[participants[0]["membre_id"]] -= reste

        for r in remboursements:
            soldes[r["payeur_id"]] += r["montant_centimes"]
            soldes[r["beneficiaire_id"]] -= r["montant_centimes"]

    return soldes


if __name__ == "__main__":
    app.run(debug=True)