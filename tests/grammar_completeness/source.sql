-- Synthetic source for grammar-completeness test (NOT a real Northwind / customers dataset).
-- Designed to give every currently-unused SMILE op a meaningful surface:
--   ADD_UNIQUE_KEY     → on customers.email
--   DELETE_UNIQUE_KEY  → undoes the above
--   COPY_PROPERTY      → email customers → orders
--   MOVE_PROPERTY      → sku   products  → customers
--   COPY_ENTITY        → customers AS customers_archive
--   CAST_ENTITY        → products TO DOCUMENT (kind_locked)
--   RECARD             → orders.customer_id cardinality
--   DELETE_EMBEDDED    → set up via ADD_EMBEDDED then delete
--   DELETE_LABEL       → set up via ADD_LABEL    then delete

CREATE TABLE customers (
    id         INTEGER PRIMARY KEY,
    email      VARCHAR(255),
    full_name  VARCHAR(255)
);

CREATE TABLE orders (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER REFERENCES customers(id),
    amount       DECIMAL
);

CREATE TABLE products (
    id    INTEGER PRIMARY KEY,
    label VARCHAR(255),
    sku   VARCHAR(255)
);
