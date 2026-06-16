CREATE DATABASE IF NOT EXISTS helpmedraft
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE helpmedraft;

CREATE TABLE utilisateur (
    Id_utilisateur INT AUTO_INCREMENT,
    nom VARCHAR(50) NOT NULL,
    email VARCHAR(50) NOT NULL,
    mot_de_passe_hash VARCHAR(255) NOT NULL,
    prenom VARCHAR(50) NOT NULL,
    role TINYINT(1) NOT NULL DEFAULT 0,
    actif TINYINT(1) NOT NULL DEFAULT 1,
    date_inscription DATETIME,
    quota_restant INT DEFAULT 20,
    PRIMARY KEY (Id_utilisateur),
    UNIQUE (email)
);

CREATE TABLE dossier (
    Id_dossier INT AUTO_INCREMENT,
    nom VARCHAR(20) NOT NULL,
    date_creation DATETIME,
    Id_utilisateur INT NOT NULL,
    PRIMARY KEY (Id_dossier),
    FOREIGN KEY (Id_utilisateur) REFERENCES utilisateur(Id_utilisateur)
);

CREATE TABLE document (
    Id_document INT AUTO_INCREMENT,
    titre VARCHAR(255) NOT NULL,
    contenu TEXT NOT NULL,
    date_creation DATETIME,
    derniere_modification DATETIME,
    Id_dossier INT,
    Id_utilisateur INT NOT NULL,
    PRIMARY KEY (Id_document),
    FOREIGN KEY (Id_dossier) REFERENCES dossier(Id_dossier),
    FOREIGN KEY (Id_utilisateur) REFERENCES utilisateur(Id_utilisateur)
);

CREATE TABLE interaction (
    Id_interaction INT AUTO_INCREMENT,
    type_action VARCHAR(12),
    texte_entree TEXT,
    texte_sortie TEXT,
    date_ DATETIME,
    Id_utilisateur INT NOT NULL,
    Id_document INT NOT NULL,
    PRIMARY KEY (Id_interaction),
    FOREIGN KEY (Id_utilisateur) REFERENCES utilisateur(Id_utilisateur),
    FOREIGN KEY (Id_document) REFERENCES document(Id_document)
);

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
