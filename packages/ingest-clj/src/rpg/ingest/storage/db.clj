(ns rpg.ingest.storage.db
  (:require [next.jdbc :as jdbc]))

(def default-database-url
  "sqlite:////workspace/data/rpg_assistant.db")

(defn database-url []
  (or (System/getenv "DATABASE_URL") default-database-url))

(defn- sqlite-file-path [database-url]
  (let [prefix "sqlite:///"]
    (if-not (.startsWith database-url prefix)
      (throw (ex-info "Only sqlite DATABASE_URL is supported"
                      {:database-url database-url}))
      (let [path (subs database-url (count prefix))]
        (if (.startsWith path "/")
          path
          (.getAbsolutePath (java.io.File. path)))))))

(defn datasource []
  (let [file-path (sqlite-file-path (database-url))
        file (java.io.File. file-path)
        parent-file (.getParentFile file)]
    (when parent-file (.mkdirs parent-file))
    (jdbc/get-datasource {:jdbcUrl (str "jdbc:sqlite:" file-path)
                          :foreignKeys true})))

(defn with-connection [callback]
  (with-open [connection (jdbc/get-connection (datasource))]
    (jdbc/execute! connection ["PRAGMA foreign_keys = ON"])
    (callback connection)))
