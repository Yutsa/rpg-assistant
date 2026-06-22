(ns rpg.ingest.schema
  (:require [malli.core :as m]))

(def Bbox
  [:map
   [:x0 number?]
   [:y0 number?]
   [:x1 number?]
   [:y1 number?]])

(def PageBlock
  [:map
   [:block-index int?]
   [:text string?]
   [:bbox Bbox]
   [:metadata [:map-of keyword? any?]]])

(def PageOutput
  [:map
   [:page-number pos-int?]
   [:width pos?]
   [:height pos?]
   [:blocks [:sequential PageBlock]]])

(def DocumentOutput
  [:map
   [:extraction-method string?]
   [:provider-id string?]
   [:page-count pos-int?]
   [:pages [:sequential PageOutput]]])

(defn validate [schema value label]
  (if (m/validate schema value)
    value
    (throw (ex-info (str "Invalid " label)
                    {:schema (m/form schema)
                     :errors (m/explain schema value)}))))
