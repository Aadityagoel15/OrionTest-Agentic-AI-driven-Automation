Feature: Search Functionality

Background:
  Given the user navigates to "https://example.com"

Scenario: User searches for a product
  When the user enters "laptop" into the "search" field
  When the user clicks the "Search" button
  Then the user should see text "Search results for: laptop"

Scenario: User searches with no results
  When the user enters "xyznonexistent123" into the "search" field
  When the user clicks the "Search" button
  Then the user should see text "No results found"

Scenario: User searches and selects a result
  When the user enters "smartphone" into the "search" field
  When the user clicks the "Search" button
  When the user clicks the "View Details" button for the item "Premium Smartphone"
  Then the user should be on the product page
  Then the user should see text "Premium Smartphone"
