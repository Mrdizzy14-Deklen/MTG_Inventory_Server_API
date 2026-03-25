CREATE TABLE IF NOT EXISTS users (
	id INT AUTO_INCREMENT PRIMARY KEY,
	username VARCHAR(50) UNIQUE NOT NULL,
	password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS ref_cards (
	oracle_id VARCHAR(36) NOT NULL,
    card_name VARCHAR(255) NOT NULL,
    type_line VARCHAR(255) NOT NULL,
    mana_cost INT DEFAULT 0 NOT NULL,
    rarity VARCHAR(20) NOT NULL,
	text_box TEXT,
	power VARCHAR(10),
	toughness VARCHAR(10),
	w BOOLEAN DEFAULT 0,
	u BOOLEAN DEFAULT 0,
	b BOOLEAN DEFAULT 0,
	r BOOLEAN DEFAULT 0,
	g BOOLEAN DEFAULT 0,

	PRIMARY KEY (oracle_id)
);

CREATE TABLE IF NOT EXISTS inventory (
	id INT AUTO_INCREMENT,
	user_id INT NOT NULL,
	oracle_id VARCHAR(36) NOT NULL,
	quantity INT DEFAULT 1 NOT NULL,
	
	PRIMARY KEY (id),
	CONSTRAINT owned_by FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
	CONSTRAINT card_info FOREIGN KEY (oracle_id) REFERENCES ref_cards(oracle_id),
	CONSTRAINT user_card_id UNIQUE (user_id, oracle_id),
	CONSTRAINT positive_cards CHECK (quantity > 0)
);

-- 2026-03-24
CREATE TABLE IF NOT EXISTS meta_data (
    meta_key VARCHAR(50) PRIMARY KEY,
    meta_value VARCHAR(100)
);

-- 2026-03-25
CREATE TABLE IF NOT EXISTS trade_preferences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    oracle_id VARCHAR(255) DEFAULT NULL, -- NULL means general preference
    tag VARCHAR(50) DEFAULT NULL, -- General title for preference
    notes TEXT, -- User notes about this preference
    trade_status ENUM('for_trade', 'looking_for', 'not_for_trade') NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE KEY unique_user_pref (user_id, oracle_id, tag)
);