(ns rpg.ingest.pipeline
  "Phase 0 import: extract PDFBox pages + blocks and persist to SQLite."
  (:require [clojure.string :as str]
            [next.jdbc :as jdbc]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.ids :as ids]
            [rpg.ingest.storage.db :as db]
            [rpg.ingest.storage.raw :as raw]))

(defn- page-text [blocks]
  (->> blocks (map :text) (str/join "\n\n") str/trim))

(defn- build-page-records
  [document-id extracted]
  (let [pages (:pages extracted)]
    (reduce
     (fn [acc page]
       (let [page-number (:page-number page)
             blocks (:blocks page)
             page-id (ids/page-id document-id page-number)
             text (page-text blocks)
             page-record {:id page-id
                          :document-id document-id
                          :page-number page-number
                          :text text
                          :extraction-method "pdfbox"
                          :has-text (boolean (seq text))
                          :text-coverage-ratio 0.0
                          :width (:width page)
                          :height (:height page)}
             block-records (mapv
                            (fn [block]
                              {:id (ids/page-block-id document-id page-number (:block-index block))
                               :document-id document-id
                               :page-id page-id
                               :page-number page-number
                               :block-index (:block-index block)
                               :text (:text block)
                               :bbox (:bbox block)
                               :metadata (:metadata block)})
                            blocks)]
         {:pages (conj (:pages acc) page-record)
          :blocks (into (:blocks acc) block-records)}))
     {:pages [] :blocks []}
     pages)))

(defn import-pdf!
  "Import a PDF: pages + page_blocks only (phase 0). Returns result map."
  [{:keys [pdf-path campaign-id campaign-title game-system reimport db-spec]
    :or {reimport true}}]
  (let [run-id (ids/new-id "run")
        content-hash (ids/hash-file pdf-path)
        document-id (ids/document-id-from-hash content-hash)
        ds (db/connect :db-spec db-spec)]
    (raw/ensure-campaign! ds campaign-id :title campaign-title :game-system game-system)
    (raw/create-ingestion-run! ds {:id run-id
                                   :campaign-id campaign-id
                                   :status "running"})
    (try
      (let [extracted (pdf/extract-document pdf-path)
            {:keys [pages blocks]} (build-page-records document-id extracted)
            page-count (count pages)
            block-count (count blocks)]
        (raw/upsert-document! ds document-id campaign-id
                              (.getName (java.io.File. pdf-path))
                              page-count content-hash)
        (raw/update-ingestion-run! ds run-id :document-id document-id)
        (when reimport
          (raw/delete-document-raw-data! ds document-id))
        (jdbc/with-transaction [tx ds]
          (raw/insert-pages! tx pages)
          (raw/insert-page-blocks! tx blocks))
        (let [stats {:page_count page-count
                     :block_count block-count
                     :source_pdf_path (.getAbsolutePath (java.io.File. pdf-path))
                     :extraction_method "pdfbox"}]
          (raw/update-ingestion-run! ds run-id
                                     :status "completed"
                                     :stats stats
                                     :finished true)
          {:ingestion-run-id run-id
           :campaign-id campaign-id
           :document-id document-id
           :status "completed"
           :stats stats}))
      (catch Exception e
        (raw/update-ingestion-run! ds run-id
                                   :status "failed"
                                   :error-message (.getMessage e)
                                   :finished true)
        {:ingestion-run-id run-id
         :campaign-id campaign-id
         :document-id document-id
         :status "failed"
         :error-message (.getMessage e)}))))
