(ns rpg.ingest.import-test
  (:require [clojure.test :refer [deftest is testing]]
            [next.jdbc :as jdbc]
            [rpg.ingest.ids :as ids]
            [rpg.ingest.pipeline :as pipeline]
            [rpg.ingest.storage.db :as db]
            [rpg.ingest.storage.raw :as raw]
            [rpg.ingest.test-db :as test-db]
            [rpg.ingest.test-fixtures.pdf :as sample-pdf])
  (:import [java.io File]))

(defn- import-sample!
  [db-path pdf-path campaign-id & {:keys [coverage-threshold]
                                   :or {coverage-threshold 0.0}}]
  (pipeline/import-pdf!
   {:pdf-path pdf-path
    :campaign-id campaign-id
    :db-spec db-path
    :coverage-threshold coverage-threshold}))

(deftest import-persists-pages-blocks-sections-and-chunks
  (testing "Full pipeline: synthetic PDF → SQLite pages, blocks, sections, chunks"
    (let [{:keys [db-path]} (test-db/temp-database)
          pdf-file (doto (File/createTempFile "rpg-import-" ".pdf")
                     (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath pdf-file))
          result (import-sample! db-path pdf-path "test-campaign")
          ds (db/connect :db-spec db-path)
          document-id (:document-id result)]
      (is (= "completed" (:status result))
          (str "import failed: " (:error-message result)))
      (is (raw/campaign-exists? ds "test-campaign"))
      (is (= document-id (:id (raw/get-document ds document-id))))
      (is (= 1 (raw/count-rows ds "pages" document-id)))
      (is (pos? (raw/count-rows ds "page_blocks" document-id)))
      (is (pos? (raw/count-rows ds "sections" document-id)))
      (is (pos? (raw/count-rows ds "chunks" document-id)))
      (let [run (raw/get-ingestion-run ds (:ingestion-run-id result))]
        (is (= "completed" (:status run)))
        (is (some? (:finished_at run)))
        (is (= "pdfbox" (:extraction_method (:stats run))))
        (is (= 1 (:page_count (:stats run))))
        (is (pos? (:section_count (:stats run))))
        (is (pos? (:chunk_count (:stats run))))
        (is (number? (:text_coverage_ratio (:stats run))))))))

(deftest import-document-id-derived-from-pdf-hash
  (testing "document_id is stable from PDF content hash"
    (let [{:keys [db-path]} (test-db/temp-database)
          pdf-file (doto (File/createTempFile "rpg-import-hash-" ".pdf")
                     (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath pdf-file))
          expected-doc (ids/document-id-from-hash (ids/hash-file pdf-path))
          result (import-sample! db-path pdf-path "hash-campaign")]
      (is (= expected-doc (:document-id result))))))

(deftest import-momie-pdf-when-available
  (testing "Reference COF2 PDF: 20 pages, sections and chunks populated"
    (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie)
        (let [{:keys [db-path]} (test-db/temp-database)
              result (import-sample! db-path (.getAbsolutePath momie) "momie"
                                     :coverage-threshold 0.3)
              ds (db/connect :db-spec db-path)
              document-id (:document-id result)]
          (is (= "completed" (:status result))
              (str "import failed: " (:error-message result)))
          (is (= 20 (raw/count-rows ds "pages" document-id)))
          (is (> (raw/count-rows ds "page_blocks" document-id) 150))
          (is (> (raw/count-rows ds "sections" document-id) 5))
          (is (> (raw/count-rows ds "chunks" document-id) 50))
          (let [run (raw/get-ingestion-run ds (:ingestion-run-id result))]
            (is (= 20 (:page_count (:stats run))))
            (is (> (:block_count (:stats run)) 150))
            (is (> (:section_count (:stats run)) 5))
            (is (> (:chunk_count (:stats run)) 50))
            (is (>= (:text_coverage_ratio (:stats run)) 0.3))
            (is (>= (:stat_block_count (:stats run)) 2))
            (is (= "cof2" (:stat_block_profile (:stats run))))))))))

(deftest import-rejects-low-coverage-pdf
  (testing "Synthetic sparse PDF is rejected at default coverage threshold"
    (let [{:keys [db-path]} (test-db/temp-database)
          pdf-file (doto (File/createTempFile "rpg-reject-" ".pdf")
                     (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath pdf-file))
          result (import-sample! db-path pdf-path "reject-campaign"
                                 :coverage-threshold 0.3)
          ds (db/connect :db-spec db-path)]
      (is (= "rejected" (:status result)))
      (is (re-find #"insufficient text coverage" (:error-message result)))
      (let [run (raw/get-ingestion-run ds (:ingestion-run-id result))]
        (is (= "rejected" (:status run)))
        (is (some? (:finished_at run)))))))

(deftest import-reimport-creates-new-run
  (testing "Second import creates another ingestion run for the same document"
    (let [{:keys [db-path]} (test-db/temp-database)
          pdf-file (doto (File/createTempFile "rpg-reimport-" ".pdf")
                     (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath pdf-file))
          first-result (import-sample! db-path pdf-path "reimport-campaign")
          ds (db/connect :db-spec db-path)
          document-id (:document-id first-result)]
      (import-sample! db-path pdf-path "reimport-campaign")
      (is (= 2 (test-db/query-scalar ds
                                     "SELECT COUNT(*) FROM ingestion_runs WHERE document_id = ?"
                                     document-id)))
      (is (= 1 (raw/count-rows ds "pages" document-id)))
      (is (pos? (raw/count-rows ds "sections" document-id)))
      (is (pos? (raw/count-rows ds "chunks" document-id))))))

(deftest persisted-page-uses-pdfbox-extraction-method
  (testing "Page rows are tagged pdfbox"
    (let [{:keys [db-path]} (test-db/temp-database)
          pdf-file (doto (File/createTempFile "rpg-method-" ".pdf")
                     (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath pdf-file))
          result (import-sample! db-path pdf-path "method-campaign")
          ds (db/connect :db-spec db-path)
          document-id (:document-id result)]
      (is (= "pdfbox"
             (test-db/query-scalar ds
                                   "SELECT extraction_method FROM pages WHERE document_id = ?"
                                   document-id))))))
