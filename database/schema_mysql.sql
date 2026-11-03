-- ============================================================================
-- CLYVO VET - Schema de produção (MySQL 8.0)
-- Equivalente ao schema SQLite criado automaticamente por app/database.py
-- ============================================================================
CREATE DATABASE IF NOT EXISTS clyvo_vet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE clyvo_vet;

CREATE TABLE tutors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    email VARCHAR(120)
);

CREATE TABLE pets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tutor_id INT NOT NULL,
    name VARCHAR(80) NOT NULL,
    species ENUM('canino', 'felino') NOT NULL,
    breed VARCHAR(80),
    age DECIMAL(4,1),
    weight_kg DECIMAL(5,2),
    needs_post_op BOOLEAN NOT NULL DEFAULT FALSE,
    surgery_date DATE NULL,
    device_id VARCHAR(40) UNIQUE,
    CONSTRAINT fk_pets_tutor FOREIGN KEY (tutor_id) REFERENCES tutors(id)
);

CREATE TABLE medical_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    record_date DATE NOT NULL,
    description VARCHAR(255) NOT NULL,
    diagnosis TEXT,
    treatment TEXT,
    veterinarian VARCHAR(120),
    CONSTRAINT fk_records_pet FOREIGN KEY (pet_id) REFERENCES pets(id)
);

CREATE TABLE telemetry (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    device_id VARCHAR(40),
    temperature DECIMAL(4,1) NOT NULL,
    heart_rate SMALLINT NOT NULL,
    movement_level ENUM('REPOUSO', 'MODERADO', 'ALTO') NOT NULL,
    emergency BOOLEAN NOT NULL DEFAULT FALSE,
    risk_level TINYINT,
    risk_label VARCHAR(20),
    confidence DECIMAL(5,4),
    probabilities JSON,
    anomalies JSON,
    safety_override VARCHAR(160),
    created_at DATETIME NOT NULL,
    INDEX idx_telemetry_pet (pet_id, created_at),
    CONSTRAINT fk_telemetry_pet FOREIGN KEY (pet_id) REFERENCES pets(id)
);

CREATE TABLE alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    telemetry_id BIGINT NULL,
    source ENUM('telemetria', 'chat') NOT NULL,
    risk_level TINYINT NOT NULL,
    priority VARCHAR(40) NOT NULL,
    tutor_message TEXT NOT NULL,
    soap JSON NOT NULL,
    hypotheses JSON,
    citations JSON,
    llm_mode VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ABERTO',
    created_at DATETIME NOT NULL,
    acknowledged_at DATETIME NULL,
    CONSTRAINT fk_alerts_pet FOREIGN KEY (pet_id) REFERENCES pets(id),
    CONSTRAINT fk_alerts_telemetry FOREIGN KEY (telemetry_id) REFERENCES telemetry(id)
);

CREATE TABLE chat_messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    role ENUM('user', 'assistant') NOT NULL,
    content TEXT NOT NULL,
    llm_mode VARCHAR(80),
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_chat_pet FOREIGN KEY (pet_id) REFERENCES pets(id)
);

CREATE TABLE notifications (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    pet_id INT NOT NULL,
    alert_id BIGINT NULL,
    channel VARCHAR(40) NOT NULL,
    recipient VARCHAR(160) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'ENVIADO (simulado)',
    created_at DATETIME NOT NULL,
    CONSTRAINT fk_notif_pet FOREIGN KEY (pet_id) REFERENCES pets(id),
    CONSTRAINT fk_notif_alert FOREIGN KEY (alert_id) REFERENCES alerts(id)
);

-- Dados de exemplo (os mesmos do seed automático)
INSERT INTO tutors (name, phone, email) VALUES
    ('Mariana Silva', '+55 11 98888-1001', 'mariana@example.com'),
    ('Rafael Souza', '+55 11 97777-2002', 'rafael@example.com'),
    ('Helena Prado', '+55 11 96666-3003', 'helena@example.com');

INSERT INTO pets (tutor_id, name, species, breed, age, weight_kg, needs_post_op, surgery_date, device_id) VALUES
    (1, 'Thor', 'canino', 'Golden Retriever', 4, 32.0, TRUE, CURDATE() - INTERVAL 4 DAY, 'CLYVO-COLLAR-01'),
    (2, 'Luna', 'felino', 'SRD (sem raça definida)', 2, 3.8, TRUE, CURDATE() - INTERVAL 1 DAY, 'CLYVO-COLLAR-02'),
    (3, 'Bob', 'canino', 'Beagle', 12, 14.5, FALSE, NULL, 'CLYVO-COLLAR-03');

INSERT INTO medical_records (pet_id, record_date, description, diagnosis, treatment, veterinarian) VALUES
    (1, CURDATE() - INTERVAL 4 DAY, 'Cirurgia ortopédica de osteossíntese femoral', 'Fratura completa de fêmur direito tratada com placa e parafusos',
     'Meloxicam 0,1 mg/kg SID por 7 dias, dipirona 25 mg/kg TID por 5 dias, repouso absoluto por 6 semanas e colar elizabetano', 'Dra. Camila Torres - CRMV/SP 38421'),
    (1, CURDATE() - INTERVAL 120 DAY, 'Consulta de rotina e vacinação', 'Paciente hígido', 'Vacina polivalente V10 e antirrábica', 'Dr. André Lima - CRMV/SP 40110'),
    (2, CURDATE() - INTERVAL 1 DAY, 'Ovariosalpingohisterectomia (castração eletiva)', 'Procedimento eletivo sem intercorrências; recuperação anestésica lenta',
     'Meloxicam 0,05 mg/kg SID por 3 dias, roupa cirúrgica por 10 dias e restrição de saltos', 'Dra. Camila Torres - CRMV/SP 38421'),
    (3, CURDATE() - INTERVAL 30 DAY, 'Consulta cardiológica de acompanhamento', 'Doença valvar mitral degenerativa estágio B2',
     'Pimobendan 0,25 mg/kg BID contínuo e controle de frequência respiratória em repouso', 'Dr. Paulo Mendes - CRMV/SP 29877');
