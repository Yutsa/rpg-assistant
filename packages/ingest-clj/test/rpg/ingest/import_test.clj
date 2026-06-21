(ns rpg.ingest.import-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing use-fixtures]]
            [next.jdbc :as jdbc]
            [rpg.ingest.import :as import]
            [rpg.ingest.storage.db :as db]
            [rpg.ingest.storage.ids :as ids]
            [rpg.ingest.storage.raw :as raw]
            [rpg.ingest.test-fixtures.pdf :as sample-pdf])
  (:import [java.io File]))

(defn- temp-database-url [temp-file]
  (str "sqlite:///" (.getAbsolutePath temp-file)))

(defn- run-migration [connection sql-path]
  (doseq [statement (.split (slurp sql-path) ";")]
    (let [sql (str/trim statement)]
      (when (seq sql)
        (jdbc/execute! connection [sql])))))

(defn with-temp-database [test-function]
  (let [database-file (File/createTempFile "rpg-ingest-test-" ".db")]
    (try
      (with-redefs [db/database-url #(temp-database-url database-file)]
        (db/with-connection
          (fn [connection]
            (run-migration connection "resources/migrations/001_raw_minimal.sql")
            (test-function connection database-file))))
      (finally
        (.delete database-file)))))

(deftest content-hash-is-stable
  (testing "Document id follows the Python hash prefix"
    (with-temp-database
      (fn [_ _]
        (let [temp-file (doto (File/createTempFile "rpg-hash-" ".pdf")
                          (.deleteOnExit))
              pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
              hash-value (ids/content-hash pdf-path)]
          (is (= 64 (count hash-value)))
          (is (= (str "doc_" (subs hash-value 0 12))
                 (ids/document-id-from-hash hash-value))))))))

(deftest run-import-persists-pages-and-blocks
  (testing "Import stores raw pages and blocks in sqlite"
    (with-temp-database
      (fn [_ _]
        (let [temp-file (doto (File/createTempFile "rpg-import-" ".pdf")
                          (.deleteOnExit))
              pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
              result (import/run-import pdf-path {:campaign-id "test-campaign"})
              document-id (:document-id result)]
          (is (= "completed" (:status result)))
          (db/with-connection
            (fn [connection]
              (is (pos? (raw/count-page-blocks connection document-id))))))))))

(use-fixtures :each (fn [test-function] (test-function)))
