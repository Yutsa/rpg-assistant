(ns rpg.ingest.storage.raw
  (:require [cheshire.core :as json]
            [clojure.string :as str]
            [next.jdbc :as jdbc])
  (:import [java.time Instant]))

(defn- utc-now []
  (str (Instant/now)))

(defn- json-string [value]
  (json/generate-string value {:key-fn name}))

(defn ensure-campaign [connection campaign-id & {:keys [title game-system]}]
  (jdbc/execute! connection
                 ["INSERT OR IGNORE INTO campaigns (id, title, game_system) VALUES (?, ?, ?)"
                  campaign-id (or title campaign-id) (or game-system "")]))

(defn create-ingestion-run [connection run-id campaign-id]
  (jdbc/execute! connection
                 ["INSERT INTO ingestion_runs
                   (id, campaign_id, stage, status, stats, started_at)
                   VALUES (?, ?, 'raw', 'running', '{}', ?)"
                  run-id campaign-id (utc-now)]))

(defn update-ingestion-run
  [connection run-id & {:keys [status document-id error-message stats finished?]}]
  (let [assignments (cond-> []
                      status (conj ["status" status])
                      document-id (conj ["document_id" document-id])
                      error-message (conj ["error_message" error-message])
                      stats (conj ["stats" (json-string stats)])
                      finished? (conj ["finished_at" (utc-now)]))
        set-clause (str/join ", " (map #(str (first %) " = ?") assignments))
        params (vec (map second assignments))]
    (when (seq assignments)
      (jdbc/execute! connection
                     (into [(str "UPDATE ingestion_runs SET " set-clause " WHERE id = ?")]
                           (concat params [run-id]))))))

(defn upsert-document
  [connection document-id campaign-id filename page-count hash-value]
  (jdbc/execute! connection
                 ["INSERT INTO documents
                   (id, campaign_id, filename, page_count, content_hash)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (id) DO UPDATE SET
                     filename = excluded.filename,
                     page_count = excluded.page_count,
                     content_hash = excluded.content_hash"
                  document-id campaign-id filename page-count hash-value]))

(defn delete-document-raw-data [connection document-id]
  (doseq [statement ["DELETE FROM chunks WHERE document_id = ?"
                     "DELETE FROM sections WHERE document_id = ?"
                     "DELETE FROM page_blocks WHERE document_id = ?"
                     "DELETE FROM pages WHERE document_id = ?"]]
    (jdbc/execute! connection (into [statement] [document-id]))))

(defn insert-pages [connection page-rows]
  (doseq [page page-rows]
    (jdbc/execute! connection
                   ["INSERT INTO pages
                     (id, document_id, page_number, text, extraction_method,
                      has_text, text_coverage_ratio, width, height)
                     VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                     ON CONFLICT (document_id, page_number) DO UPDATE SET
                       text = excluded.text,
                       extraction_method = excluded.extraction_method,
                       has_text = excluded.has_text,
                       width = excluded.width,
                       height = excluded.height"
                    (:id page) (:document-id page) (:page-number page)
                    (:text page) (:extraction-method page) (:has-text page)
                    (:width page) (:height page)])))

(defn insert-page-blocks [connection block-rows]
  (doseq [block block-rows]
    (jdbc/execute! connection
                   ["INSERT INTO page_blocks
                     (id, document_id, page_id, page_number, block_index, text,
                      bbox_json, metadata_json)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (id) DO UPDATE SET
                       text = excluded.text,
                       bbox_json = excluded.bbox_json,
                       metadata_json = excluded.metadata_json"
                    (:id block) (:document-id block) (:page-id block)
                    (:page-number block) (:block-index block) (:text block)
                    (json-string (:bbox block))
                    (json-string (:metadata block))])))

(defn count-page-blocks [connection document-id]
  (-> (jdbc/execute-one! connection
                         ["SELECT COUNT(*) AS count FROM page_blocks WHERE document_id = ?"
                          document-id])
      :count))
