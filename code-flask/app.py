from flask import Flask, redirect, render_template_string, request

from base import ouvrir_base

# Le HTML de la page.
PAGE = """
<body style="background-image: url('{{ url_for('static', filename='photo.png') }}'); background-size: 1400px; background-repeat: no-repeat;">
  
  <h1>Partage de frais</h1> 

  <div style="text-align: center;">
    <img src="{{ url_for('static', filename='transparent.png') }}" alt="Logo" width="600" height="400">
  </div>

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

  <h2>Groupes</h2>
  <ul>
    {% for groupe in groupes %}
      <li>{{ groupe["nom"] }}</li>
    {% endfor %}
  </ul>

  <form method="post" action="/groupes">
    <input name="nom" placeholder="Nom" required>
    <input name="date_debut" type="date" required>
    <input name="date_fin" type="date" required>
    <button>Ajouter</button>
  </form>

  <h2>Dépenses</h2>
  <form method="post" action="/depenses">
    <input name="groupe_id" placeholder="ID du groupe" required>
    <input name="libelle" placeholder="Libellé" required>
    <input name="montant_centimes" type="number" placeholder="Montant (en centimes)" required>
    <input name="date" type="date" required>
    <input name="payeur_id" placeholder="ID du payeur" required>
    <input name="participants" placeholder="IDs des participants (séparés par des virgules)" required>
    <button>Ajouter</button>
  </form>

  <h2>Supprimer une dépense</h2>
  <form method="post" action="/depenses/supprimer">
    <input name="id" placeholder="ID de la dépense" required>
    <button>Supprimer</button>
  </form>


</body>
"""

app = Flask(__name__)


# Page d'accueil : lit les membres et affiche PAGE.
@app.get("/")
def accueil():
    with ouvrir_base() as conn:
        membres = conn.execute(
            "SELECT id, nom, groupe_id FROM membres"
        ).fetchall()

        groupes = conn.execute(
            "SELECT id, nom FROM groupes"
        ).fetchall()

    soldes = {}

    for groupe in groupes:
        soldes.update(calculer_soldes(groupe["id"]))

    return render_template_string(
        PAGE,
        membres=membres,
        groupes=groupes,
        soldes=soldes
    )


@app.post("/membres")
def ajouter_membre():
    nom = request.form["nom"]
    groupe_id = request.form["groupe_id"]

    with ouvrir_base() as conn:
        groupe = conn.execute(
            "SELECT id FROM groupes WHERE id = ?",
            [groupe_id]
        ).fetchone()

        if groupe is None:
            return "Groupe inexistant", 400

        conn.execute(
            "INSERT INTO membres (groupe_id, nom) VALUES (?, ?)",
            [groupe_id, nom]
        )

    return redirect("/")


@app.post("/groupes")
def ajouter_groupe():
    nom = request.form["nom"].strip()
    date_debut = request.form["date_debut"]
    date_fin = request.form["date_fin"]

    if not nom:
        return "Le nom est obligatoire", 400

    if date_debut > date_fin:
        return "La date de fin doit être après la date de début", 400

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
    montant_centimes = int(request.form["montant_centimes"])
    date = request.form["date"]
    payeur_id = request.form["payeur_id"]
    participants = request.form.getlist("participants")

    if montant_centimes <= 0:
        return "Le montant doit être positif", 400

    if not participants:
        return "Il faut au moins un participant", 400

    if len(participants) != len(set(participants)):
        return "Un participant ne peut pas être sélectionné plusieurs fois", 400

    with ouvrir_base() as conn:
        groupe = conn.execute(
            "SELECT date_debut, date_fin FROM groupes WHERE id = ?",
            [groupe_id]
        ).fetchone()

        if groupe is None:
            return "Groupe inexistant", 400

        if not (groupe["date_debut"] <= date <= groupe["date_fin"]):
            return "La dépense doit être comprise dans le séjour", 400

        membres = conn.execute(
            "SELECT id FROM membres WHERE groupe_id = ?",
            [groupe_id]
        ).fetchall()

        ids_membres = {str(membre["id"]) for membre in membres}

        if payeur_id not in ids_membres:
            return "Le payeur n'appartient pas au groupe", 400

        if any(p not in ids_membres for p in participants):
            return "Un participant n'appartient pas au groupe", 400


        depense_id = conn.execute(
            "INSERT INTO depenses (groupe_id, libelle, montant_centimes, date, payeur_id) VALUES (?, ?, ?, ?, ?)",
            [groupe_id, libelle, montant_centimes, date, payeur_id]
        ).lastrowid

        for participant_id in participants:
            conn.execute(
                "INSERT INTO participations (depense_id, membre_id) VALUES (?, ?)",
                [depense_id, participant_id]
            )

    return redirect("/")

@app.post("/depenses/supprimer")
def supprimer_depense():
    depense_id = request.form["id"]

    with ouvrir_base() as conn:
        conn.execute(
            "DELETE FROM participations WHERE depense_id = ?",
            [depense_id]
        )

        conn.execute(
            "DELETE FROM depenses WHERE id = ?",
            [depense_id]
        )

    return redirect("/")

def repartir_depense(montant_centimes, participants):
    if montant_centimes <= 0 or not participants:
        raise ValueError("Dépense invalide")

    part = montant_centimes // len(participants)
    reste = montant_centimes % len(participants)

    parts = {}

    for i, participant_id in enumerate(participants):
        parts[participant_id] = part + (reste if i == 0 else 0)

    return parts

def calculer_soldes(groupe_id):
    with ouvrir_base() as conn:
        membres = conn.execute(
            "SELECT id FROM membres WHERE groupe_id = ?",
            [groupe_id]
        ).fetchall()

        depenses = conn.execute(
            "SELECT id, montant_centimes, payeur_id FROM depenses WHERE groupe_id = ?",
            [groupe_id]
        ).fetchall()

        soldes = {membre["id"]: 0 for membre in membres}

        for depense in depenses:
            participants = conn.execute(
                "SELECT membre_id FROM participations WHERE depense_id = ? ORDER BY rowid",
                [depense["id"]]
            ).fetchall()

            ids_participants = [p["membre_id"] for p in participants]

            parts = repartir_depense(
                depense["montant_centimes"],
                ids_participants
            )

            soldes[depense["payeur_id"]] += depense["montant_centimes"]

            for membre_id, part in parts.items():
                soldes[membre_id] -= part

    return soldes


if __name__ == "__main__":
    app.run(debug=True)
