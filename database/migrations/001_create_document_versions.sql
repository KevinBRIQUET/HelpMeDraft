CREATE TABLE version_document (
    Id_version INT AUTO_INCREMENT,
    titre VARCHAR(255) NOT NULL,
    contenu TEXT NOT NULL,
    date_version DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Id_document INT NOT NULL,
    Id_utilisateur INT NOT NULL,
    PRIMARY KEY (Id_version),
    INDEX idx_version_document (Id_document, date_version),
    CONSTRAINT fk_version_document_document
        FOREIGN KEY (Id_document)
        REFERENCES document(Id_document)
        ON DELETE CASCADE,
    CONSTRAINT fk_version_document_utilisateur
        FOREIGN KEY (Id_utilisateur)
        REFERENCES utilisateur(Id_utilisateur)
        ON DELETE CASCADE
);

-- Crée une première version pour les documents déjà enregistrés.
INSERT INTO version_document (
    titre,
    contenu,
    date_version,
    Id_document,
    Id_utilisateur
)
SELECT
    doc.titre,
    doc.contenu,
    COALESCE(doc.derniere_modification, doc.date_creation, NOW()),
    doc.Id_document,
    doc.Id_utilisateur
FROM document doc
WHERE NOT EXISTS (
    SELECT 1
    FROM version_document version
    WHERE version.Id_document = doc.Id_document
);
