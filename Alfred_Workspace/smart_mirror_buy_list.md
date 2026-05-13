# Smart Mirror Hardware Shopping List

This is the master list of components required to build the physical Smart Mirror to run Alfred's "Mirror Mode".

## Core Components

- [ ] **Two-Way Glass or Acrylic** ([Amazon Search Link](https://www.amazon.com/s?k=two+way+mirror+acrylic))
  - *Tip:* Acrylic is cheaper, lighter, and easier to cut. Glass is heavier but perfectly flat (no fun-house mirror distortion).
  - *Sizing:* Order this *after* you have your monitor so you can match the dimensions exactly.

- [ ] **Flat-Screen Monitor or TV** ([Amazon Refurbished](https://www.amazon.com/s?k=refurbished+thin+computer+monitor))
  - *Tip:* Do not buy new! Find a cheap, used monitor on Facebook Marketplace, Craigslist, or at a thrift store. 
  - *Requirement:* Must have an HDMI port and be relatively thin.

- [ ] **Compute Unit (The Brain)** ([CanaKit Raspberry Pi 4 Kit](https://www.amazon.com/s?k=Raspberry+Pi+4+4GB+starter+kit))
  - *Recommendation:* Raspberry Pi 4 or Raspberry Pi 5.
  - *Alternatives:* An old laptop (with the screen removed or folded flat) or a cheap Windows Mini-PC.

- [ ] **Wooden Frame (Shadow Box)** ([IKEA SANNAHED](https://www.ikea.com/us/en/p/sannahed-frame-black-80459117/))
  - *Tip:* You need a frame deep enough to hide the monitor and the compute unit inside.
  - *Hack:* IKEA "RIBBA" or "SANNAHED" deep frames are incredibly popular for DIY smart mirrors.

## Peripherals & Wiring

- [ ] **Webcam with Built-in Microphone**
  - *Requirement:* Needed for Alfred's facial recognition (Auto-Wake) and voice commands.
  - *Tip:* Look for a low-profile USB webcam. You can disassemble the plastic casing to mount the bare circuit board flush against the glass inside the frame.

- [ ] **Cabling & Power**
  - [ ] Short HDMI cable (to connect Pi to Monitor).
  - [ ] Low-profile surge protector / power strip (to mount inside the frame so only one plug goes to the wall).
  - [ ] Power supply for the Raspberry Pi.
  - [ ] Power supply for the Monitor.

## Construction Materials

- [ ] **Black Cardboard or Matte Paper**
  - *Use:* If your monitor is smaller than your glass, you must tape black cardboard around the monitor to block any light from bleeding through the edges of the mirror.

- [ ] **Mounting Tape / Velcro**
  - *Use:* Heavy-duty double-sided tape or command strips to secure the Raspberry Pi and cables inside the frame.

---

### Recommended Build Order:
1. **Source the Monitor:** Get the screen first. Take the plastic bezel off if you feel comfortable (it makes it thinner).
2. **Measure:** Measure the exact height and width of the bare monitor.
3. **Order the Glass & Frame:** Order the two-way glass to fit exactly over the monitor, and buy a frame deep enough to hold it all.
4. **Assemble:** Frame face down $\rightarrow$ Two-way glass $\rightarrow$ Monitor (screen facing the glass) $\rightarrow$ Raspberry Pi & Cables taped to the back.
