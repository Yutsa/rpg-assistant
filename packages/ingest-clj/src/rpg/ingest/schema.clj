(ns rpg.ingest.schema
  (:require [malli.core :as m]))

(def Bbox
  [:map
   [:x0 number?]
   [:y0 number?]
   [:x1 number?]
   [:y1 number?]])

(def LayoutBlock
  [:map
   [:block-index int?]
   [:text string?]
   [:bbox Bbox]
   [:metadata [:map-of keyword? any?]]])

(def LayoutPage
  [:map
   [:page-number pos-int?]
   [:width pos?]
   [:height pos?]
   [:text string?]
   [:blocks [:sequential LayoutBlock]]])

(def LayoutDocument
  [:map
   [:source-path string?]
   [:pages [:sequential LayoutPage]]])

(def ImportResult
  [:map
   [:ingestion-run-id string?]
   [:campaign-id string?]
   [:document-id [:maybe string?]]
   [:status [:enum "pending" "running" "failed" "rejected" "completed"]]
   [:error-message [:maybe string?]]
   [:stats [:map-of keyword? any?]]])

(defn validate [schema value label]
  (if (m/validate schema value)
    value
    (throw (ex-info (str "Invalid " label)
                    {:schema (m/form schema)
                     :errors (m/explain schema value)}))))
