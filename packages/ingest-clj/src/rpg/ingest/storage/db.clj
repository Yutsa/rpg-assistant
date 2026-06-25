(ns rpg.ingest.storage.db
  (:require [clojure.java.io :as io]
            [next.jdbc :as jdbc]
            [next.jdbc.result-set :as rs]))

(def default-sqlite-path
  "data/rpg_assistant.db")

(defn- repo-root
  []
  (-> (io/file "packages/ingest-clj")
      .getAbsoluteFile
      .getParentFile
      .getParentFile
      .getAbsolutePath))

(defn- resolve-sqlite-path
  [db-spec]
  (cond
    (instance? java.io.File db-spec) (.getAbsolutePath db-spec)
    (and (string? db-spec) (.startsWith db-spec "sqlite:"))
    (let [path (subs db-spec (count "sqlite:"))
          path (if (.startsWith path "//") (subs path 2) path)]
      (if (.startsWith path "./")
        (.getAbsolutePath (io/file (repo-root) (subs path 2)))
        path))
    (string? db-spec) (.getAbsolutePath (io/file db-spec))
    :else (throw (ex-info "Unsupported database spec" {:db-spec db-spec}))))

(defn database-url
  "Resolve SQLite path from explicit spec, DATABASE_URL env, or default."
  [& {:keys [db-spec]}]
  (or db-spec
      (System/getenv "DATABASE_URL")
      (str "sqlite:" default-sqlite-path)))

(defn connect
  [& {:keys [db-spec]}]
  (let [url (database-url :db-spec db-spec)
        path (resolve-sqlite-path url)]
    (when-let [parent (.getParent (io/file path))]
      (.mkdirs (io/file parent)))
    (jdbc/get-datasource {:jdbcUrl (str "jdbc:sqlite:" path)
                          :journal_mode "WAL"})))

(defn query
  [ds sql & params]
  (apply jdbc/execute! ds (into [sql] params) {:builder-fn rs/as-unqualified-maps}))

(defn query-one
  [ds sql & params]
  (first (apply query ds sql params)))

(defn execute!
  [ds sql & params]
  (jdbc/execute! ds (into [sql] params)))

(defn with-transaction
  [ds f]
  (jdbc/with-transaction [tx ds]
    (f tx)))
