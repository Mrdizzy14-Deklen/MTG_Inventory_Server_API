CREATE TABLE users (
	id INT AUTO_INCREMENT PRIMARY KEY,
	username VARCHAR(50) UNIQUE NOT NULL,
	password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE inventory (
	id INT AUTO_INCREMENT,
	user_id INT NOT NULL,
	oracle_id VARCHAR(36) NOT NULL,
	quantity INT DEFAULT 1 NOT NULL,
	card_name VARCHAR(255) NOT NULL,
	type_line VARCHAR(255) NOT NULL,
	mana_cost INT DEFAULT 0 NOT NULL,
	rarity CHAR DEFAULT 'C' NOT NULL,
	text_box TEXT,
	power INT,
	toughness INT,
	w BOOLEAN,
	u BOOLEAN,
	b BOOLEAN,
	r BOOLEAN,
	g BOOLEAN,

	PRIMARY KEY (id),
	CONSTRAINT owned_by FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
	CONSTRAINT user_card_id UNIQUE (user_id, oracle_id),
	CONSTRAINT positive_cards CHECK (quantity > 0)
);

CREATE TABLE ref_cards (
	oracle_id VARCHAR(36) NOT NULL,
    card_name VARCHAR(255) NOT NULL,
    type_line VARCHAR(255) NOT NULL,
    mana_cost INT DEFAULT 0 NOT NULL,
    rarity CHAR DEFAULT 'C' NOT NULL,
	text_box TEXT,
	power INT,
	toughness INT,
	w BOOLEAN,
	u BOOLEAN,
	b BOOLEAN,
	r BOOLEAN,
	g BOOLEAN,

	PRIMARY KEY (oracle_id)
);

CREATE TABLE meta_data (
    meta_key VARCHAR(50) PRIMARY KEY,
    meta_value VARCHAR(100)
);