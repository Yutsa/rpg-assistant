(ns rpg.ingest.import
  (:require [clojure.string :as str]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.schema :as schema]
            [rpg.ingest.storage.db :as db]
            [rpg.ingest.storage.ids :as ids]
            [rpg.ingest.storage.raw :as raw]))

(defn- blank-text? [text]
  (str/blank? text))

(defn- page-record [document-id layout-page]
  {:id (ids/page-id document-id (:page-number layout-page))
   :document-id document-id
   :page-number (:page-number layout-page)
   :text (:text layout-page)
   :extraction-method "pdfbox"
   :has-text (if (blank-text? (:text layout-page)) 0 1)
   :width (:width layout-page)
   :height (:height layout-page)})

(defn- block-record [document-id page-record layout-block]
  {:id (ids/page-block-id document-id (:page-number page-record) (:block-index layout-block))
   :document-id document-id
   :page-id (:id page-record)
   :page-number (:page-number page-record)
   :block-index (:block-index layout-block)
   :text (:text layout-block)
   :bbox (:bbox layout-block)
   :metadata (:metadata layout-block)})

(defn- page-block-records [document-id layout-page]
  (let [page (page-record document-id layout-page)]
    {:page page
     :blocks (mapv #(block-record document-id page %) (:blocks layout-page))}))

(defn build-persistence-payload [document-id layout-document]
  (let [pages-and-blocks (mapv #(page-block-records document-id %) (:pages layout-document))
        pages (mapv :page pages-and-blocks)
        blocks (vec (mapcat :blocks pages-and-blocks))]
    {:pages pages :blocks blocks}))

(defn- completed-stats [pdf-path payload]
  {:source-pdf-path pdf-path
   :page-count (count (:pages payload))
   :block-count (count (:blocks payload))
   :extraction-method "pdfbox"
   :ingest-mode "raw"})

(defn- failed-result [run-id campaign-id error-message]
  {:ingestion-run-id run-id
   :campaign-id campaign-id
   :document-id nil
   :status "failed"
   :error-message error-message
   :stats {}})

(defn- completed-result [run-id campaign-id document-id stats]
  {:ingestion-run-id run-id
   :campaign-id campaign-id
   :document-id document-id
   :status "completed"
   :error-message nil
   :stats stats})

(defn persist-raw-document
  [connection run-id document-id campaign-id pdf-path hash-value layout-document reimport?]
  (raw/upsert-document connection document-id campaign-id
                       (.getName (java.io.File. pdf-path))
                       (count (:pages layout-document))
                       hash-value)
  (raw/update-ingestion-run connection run-id :document-id document-id)
  (when reimport?
    (raw/delete-document-raw-data connection document-id))
  (let [payload (build-persistence-payload document-id layout-document)]
    (raw/insert-pages connection (:pages payload))
    (raw/insert-page-blocks connection (:blocks payload))
    payload))

(defn run-import
  [pdf-path {:keys [campaign-id campaign-title game-system reimport?]
             :or {campaign-title "" game-system "" reimport? true}}]
  (let [run-id (ids/new-run-id)
        hash-value (ids/content-hash pdf-path)
        document-id (ids/document-id-from-hash hash-value)]
    (try
      (db/with-connection
        (fn [connection]
          (raw/ensure-campaign connection campaign-id
                               :title campaign-title :game-system game-system)
          (raw/create-ingestion-run connection run-id campaign-id)
          (let [layout-document (pdf/extract-layout pdf-path)
                payload (persist-raw-document connection run-id document-id campaign-id
                                              pdf-path hash-value layout-document reimport?)
                stats (completed-stats pdf-path payload)]
            (raw/update-ingestion-run connection run-id
                                      :status "completed"
                                      :stats stats
                                      :finished? true)
            (schema/validate schema/ImportResult
                             (completed-result run-id campaign-id document-id stats)
                             "import result"))))
      (catch Exception error
        (db/with-connection
          (fn [connection]
            (raw/update-ingestion-run connection run-id
                                      :status "failed"
                                      :error-message (.getMessage error)
                                      :finished? true)))
        (failed-result run-id campaign-id (.getMessage error))))))
