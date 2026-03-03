Feature: Login and Checkout Flow

Background:
  Given the user navigates to "https://example.com"
  Given the user enters "user@example.com" into the "username" field
  Given the user enters "password123" into the "password" field
  Given the user clicks the "Login" button

Scenario: User adds item to cart and completes checkout
  When the user clicks the "Add to cart" button for the item "Sample Product"
  When the user clicks the "Cart" button
  When the user clicks the "Checkout" button
  When the user enters "John" into the "first-name" field
  When the user enters "Doe" into the "last-name" field
  When the user enters "12345" into the "postal-code" field
  When the user clicks the "Continue" button
  When the user clicks the "Finish" button
  Then the user should see text "Thank you for your order"
